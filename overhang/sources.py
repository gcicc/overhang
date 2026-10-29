"""Fetchers for the measured series. Each returns plain JSON-serialisable data.

Every fetcher fails loudly on a schema change (a renamed column raises ``KeyError``).
``cache.refresh`` turns that into "keep the last good copy, mark the source stale",
so an upstream rename can never quietly empty a chart.

Sources and terms (see ``data/staging/SOURCES.md`` for the recon):
- METR time horizons: https://metr.org/ (no licence stated; attributed and linked)
- Epoch AI frontier models, benchmarks hub, ML hardware and data centers: CC BY 4.0,
  https://epoch.ai/data
- ARC Prize leaderboard JSON: undocumented endpoint, attributed and linked
- Manifold Markets public API: read-only, no key
"""

from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime

from overhang import net

METR_URL = "https://metr.org/assets/benchmark_results_1_1.yaml"
EPOCH_FRONTIER_URL = "https://epoch.ai/data/frontier_ai_models.csv"
EPOCH_NOTABLE_URL = "https://epoch.ai/data/notable_ai_models.csv"
EPOCH_BENCH_URL = "https://epoch.ai/data/benchmark_data.zip"
EPOCH_HARDWARE_URL = "https://epoch.ai/data/ml_hardware.csv"
EPOCH_DATACENTERS_URL = "https://epoch.ai/data/data_centers/data_centers.zip"
ARC_URL = "https://arcprize.org/media/data/leaderboard/{version}.json"
MANIFOLD_URL = "https://api.manifold.markets/v0/market/{id}"


# --- METR ------------------------------------------------------------------


def parse_simple_yaml(text: str) -> dict:
    """Parse the block-mapping subset of YAML that METR publishes.

    Handles ``key: value`` and nested ``key:`` blocks by indentation, skips list items
    and comments. Scalars stay strings; callers convert. This avoids a PyYAML
    dependency for one flat file. Anything outside this subset is ignored, and the
    fetcher's own key lookups fail loudly if the shape changes.
    """
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#") or stripped.startswith("- "):
            continue
        indent = len(line) - len(stripped)
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value = value.strip()
        if value:
            parent[key.strip()] = value.strip("'\"")
        else:
            child: dict = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return root


def fetch_metr() -> dict:
    doc = parse_simple_yaml(net.get(METR_URL).text)
    points = []
    for model, row in doc["results"].items():
        p50 = row["metrics"]["p50_horizon_length"]
        points.append(
            {
                "model": model,
                "date": row["release_date"],
                "value": float(p50["estimate"]),
                "ci_low": float(p50["ci_low"]),
                "ci_high": float(p50["ci_high"]),
                "is_sota": row["metrics"].get("is_sota") == "true",
            }
        )
    points.sort(key=lambda p: p["date"])
    published = doc.get("doubling_time_in_days", {}).get("from_2023_on", {})
    return {
        "benchmark": doc.get("benchmark_name"),
        "unit": "minutes",
        "points": points,
        "published_doubling_days_2023_on": _maybe_float(published.get("point_estimate")),
        "source_url": "https://metr.org/",
    }


# --- Epoch -----------------------------------------------------------------


def sector(categorization: str) -> str:
    """Epoch lists one category per organisation ("Industry,Academia"); collapse to one."""
    parts = {p.strip() for p in categorization.split(",") if p.strip()}
    if parts == {"Academia"}:
        return "academia"
    if parts == {"Industry"}:
        return "industry"
    if parts >= {"Academia", "Industry"}:
        return "both"
    return "other"


def fetch_epoch_notable() -> dict:
    """Epoch Notable AI Models since 1950: the History backbone. Rows without compute are
    counted, not imputed."""
    rows = list(csv.DictReader(io.StringIO(net.get(EPOCH_NOTABLE_URL).text)))
    points, missing = [], 0
    for r in rows:
        flop = _maybe_float(r["Training compute (FLOP)"])
        date = r["Publication date"]
        if flop is None or not date:
            missing += 1
            continue
        points.append(
            {
                "model": r["Model"],
                "org": r["Organization"],
                "date": date,
                "value": flop,
                "sector": sector(r["Organization categorization"]),
            }
        )
    points.sort(key=lambda p: p["date"])
    return {
        "unit": "FLOP",
        "points": points,
        "rows_without_compute": missing,
        "rows_total": len(rows),
        "source_url": "https://epoch.ai/data/notable-ai-models",
    }


def fetch_epoch_compute() -> dict:
    rows = list(csv.DictReader(io.StringIO(net.get(EPOCH_FRONTIER_URL).text)))
    points, missing = [], 0
    for r in rows:
        flop = _maybe_float(r["Training compute (FLOP)"])
        date = r["Publication date"]
        if flop is None or not date:
            missing += 1
            continue
        points.append(
            {
                "model": r["Model"],
                "org": r["Organization"],
                "country": r["Country (of organization)"],
                "date": date,
                "value": flop,
            }
        )
    points.sort(key=lambda p: p["date"])
    return {
        "unit": "FLOP",
        "points": points,
        "rows_without_compute": missing,
        "rows_total": len(rows),
        "source_url": "https://epoch.ai/data/frontier-ai-models",
    }


def fetch_frontiermath() -> dict:
    blob = zipfile.ZipFile(io.BytesIO(net.get(EPOCH_BENCH_URL).content))
    name = next(
        n
        for n in blob.namelist()
        if n.lower().endswith("/frontiermath.csv") or n.lower() == "frontiermath.csv"
    )
    rows = list(csv.DictReader(io.StringIO(blob.read(name).decode("utf-8"))))
    points = []
    for r in rows:
        score = _maybe_float(r["mean_score"])
        if score is None or not r["Release date"]:
            continue
        points.append(
            {
                "model": r["Model version"],
                "org": r["Organization"],
                "date": r["Release date"],
                "value": score,
            }
        )
    points.sort(key=lambda p: p["date"])
    return {
        "unit": "fraction solved",
        "points": points,
        "source_url": "https://epoch.ai/benchmarks/frontiermath",
    }


# Benchmarks from the hub that feed the Race and the quality tiles. Keys are the CSV
# stems inside the zip; METR's own file has no organisation column, so the Race reads
# Epoch's external copy of it, which does.
EPOCH_BENCHMARKS = {
    "gpqa_diamond": ("GPQA Diamond", "mean_score"),
    "swe_bench_verified": ("SWE-bench Verified", "mean_score"),
    "frontiermath_tiers_1_3_v2": ("FrontierMath T1–3", "mean_score"),
    "metr_time_horizons_external": ("METR time horizon", "Time horizon"),
}


def fetch_epoch_benchmarks() -> dict:
    blob = zipfile.ZipFile(io.BytesIO(net.get(EPOCH_BENCH_URL).content))
    by_stem = {n.rsplit("/", 1)[-1].lower().removesuffix(".csv"): n for n in blob.namelist()}
    out = {}
    for stem, (label, column) in EPOCH_BENCHMARKS.items():
        rows = list(csv.DictReader(io.StringIO(blob.read(by_stem[stem]).decode("utf-8"))))
        points = []
        for r in rows:
            value = _maybe_float(r[column])
            if value is None or not r["Release date"]:
                continue
            points.append(
                {
                    "model": r["Model version"],
                    "org": r["Organization"],
                    "date": r["Release date"],
                    "value": value,
                }
            )
        points.sort(key=lambda p: p["date"])
        out[stem] = {"label": label, "points": points}
    return {"benchmarks": out, "source_url": "https://epoch.ai/benchmarks"}


def fetch_epoch_hardware() -> dict:
    """ML accelerators with dense 16-bit tensor throughput and a release date.

    16-bit is the comparison column because every generation reports it; FP8 and FP4
    figures exist only for recent chips and would inflate the trend.
    """
    rows = list(csv.DictReader(io.StringIO(net.get(EPOCH_HARDWARE_URL).text)))
    chips, undated = [], 0
    for r in rows:
        flops = _maybe_float(r["Tensor-FP16/BF16 performance (FLOP/s)"])
        if flops is None:
            continue
        if not r["Release date"]:
            undated += 1
            continue
        chips.append(
            {
                "model": r["Hardware name"],
                "org": r["Manufacturer"],
                "date": r["Release date"][:10],
                "value": flops,
                "price_usd": _maybe_float(r["Release price (USD)"]),
            }
        )
    chips.sort(key=lambda c: c["date"])
    return {
        "chips": chips,
        "rows_total": len(rows),
        "undated_with_flops": undated,
        "source_url": "https://epoch.ai/data/machine-learning-hardware",
    }


def fetch_epoch_datacenters() -> dict:
    """Frontier data centers: owner, plus a dated H100-equivalent timeline per site.

    Owners carry a confidence tag in the source ("Amazon #confident"); the tag is split
    off and kept. Timeline rows dated in the future are Epoch's projections from permits
    and announcements; they are kept and labelled, never mixed into "current".
    """
    blob = zipfile.ZipFile(io.BytesIO(net.get(EPOCH_DATACENTERS_URL).content))
    sites = list(csv.DictReader(io.StringIO(blob.read("data_centers.csv").decode("utf-8"))))
    owners = {}
    for r in sites:
        owner, _, tag = r["Owner"].partition("#")
        owners[r["Name"]] = {
            "owner": owner.strip() or "Owner not stated",
            "confidence": tag.strip(),
        }
    timeline = []
    rows = blob.read("data_center_timelines.csv").decode("utf-8")
    for r in csv.DictReader(io.StringIO(rows)):
        h100e = _maybe_float(r["H100 equivalents"])
        if h100e is None or not r["Date"]:
            continue
        timeline.append({"site": r["Data center"], "date": r["Date"][:10], "h100e": h100e})
    timeline.sort(key=lambda t: (t["site"], t["date"]))
    return {
        "owners": owners,
        "timeline": timeline,
        "source_url": "https://epoch.ai/data/ai-data-centers",
    }


# --- ARC Prize -------------------------------------------------------------


def fetch_arc() -> dict:
    out = {"source_url": "https://arcprize.org/leaderboard", "series": {}}
    for version, label in (("v1", "ARC-AGI-1"), ("v2", "ARC-AGI-2")):
        doc = net.get(ARC_URL.format(version=version)).json()
        points, reference = [], []
        for e in doc["evaluations"]:
            if not str(e["datasetId"]).endswith("Semi_Private"):
                continue
            score = _maybe_float(e.get("score"))
            if score is None:
                continue
            if e.get("modelReleaseDate"):
                points.append(
                    {
                        "model": e["modelDisplayName"],
                        "org": e.get("providerDisplayName"),
                        "date": e["modelReleaseDate"][:10],
                        "value": score,
                    }
                )
            else:
                # Undated rows are reference panels (e.g. ARC's "Human Panel"), shown as
                # labelled reference lines, never plotted as a model.
                reference.append({"label": e["modelDisplayName"], "value": score})
        points.sort(key=lambda p: p["date"])
        out["series"][label] = {
            "unit": "fraction solved",
            "points": points,
            "reference": reference,
            "generated_at": doc.get("generatedAt"),
        }
    return out


# --- Manifold --------------------------------------------------------------


def fetch_manifold(markets: list[dict]) -> dict:
    """Current probability for each curated market in ``data/curated/manifold_markets.csv``."""
    out = []
    for m in markets:
        doc = net.get(MANIFOLD_URL.format(id=m["id"])).json()
        out.append(
            {
                **m,
                "question": doc["question"],
                "probability": doc.get("probability"),
                "volume": doc.get("volume"),
                "resolved": doc.get("isResolved", False),
                "url": doc.get("url"),
            }
        )
    return {
        "markets": out,
        "observed_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_url": "https://manifold.markets/",
    }


def _maybe_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
