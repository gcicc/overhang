"""Fetchers for the measured series. Each returns plain JSON-serialisable data.

Every fetcher fails loudly on a schema change (a renamed column raises ``KeyError``).
``cache.refresh`` turns that into "keep the last good copy, mark the source stale",
so an upstream rename can never quietly empty a chart.

Sources and terms (see ``data/staging/SOURCES.md`` for the recon):
- METR time horizons: https://metr.org/ (no licence stated; attributed and linked)
- Epoch AI frontier models and benchmarks hub: CC BY 4.0, https://epoch.ai/data
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
EPOCH_BENCH_URL = "https://epoch.ai/data/benchmark_data.zip"
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


def fetch_epoch_compute() -> dict:
    rows = list(csv.DictReader(io.StringIO(net.get(EPOCH_FRONTIER_URL).text)))
    points, missing = [], 0
    for r in rows:
        flop = _maybe_float(r["Training compute (FLOP)"])
        date = r["Publication date"]
        if flop is None or not date:
            missing += 1
            continue
        points.append({"model": r["Model"], "org": r["Organization"], "date": date, "value": flop})
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
