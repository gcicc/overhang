"""OVERHANG entry point.

    python run.py             # refresh what has gone stale, then render
    python run.py --force     # refresh everything regardless of cache age
    python run.py --render    # render from cache only, no network at all

Curated ledgers in ``data/curated/`` are validated on every run, and an invalid row
stops the build (SPEC D2). Measured sources refresh on their own ``max_age``
(``overhang/cache.py``).
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

from overhang import cache, charts, curated, quotecheck, resolve, sources, trend
from overhang.render import render

ROOT = Path(__file__).resolve().parent

# METR excludes points whose central p50 estimate exceeds 16 hours from its own
# doubling-time fit; the same rule is applied here so the two estimates are comparable.
METR_FIT_START = "2023-01-01"
METR_FIT_MAX_MINUTES = 16 * 60
METR_THRESHOLDS = (
    ("1 work-day (8 h)", 8 * 60.0),
    ("1 work-week (40 h)", 40 * 60.0),
    ("1 work-month (167 h)", 167 * 60.0),
)
COMPUTE_FIT_START = "2018-01-01"


def cached(name: str):
    env = cache.load(name)
    return env["data"] if env else None


def measured_metr(today: float) -> dict | None:
    d = cached("metr")
    if not d or not d["points"]:
        return None
    pts = d["points"]
    front = trend.frontier(pts)
    fit_pts = [p for p in front if p["value"] <= METR_FIT_MAX_MINUTES]
    fit = trend.fit_doubling(fit_pts, METR_FIT_START)
    best = trend.best_to_date(pts)
    return {
        "fit": fit,
        "best": best,
        "best_label": charts.fmt_minutes(best["value"]),
        "published": d.get("published_doubling_days_2023_on"),
        "latest": pts[-1]["date"],
        "crossings": [
            {"label": label, "date": trend.crossing_date(fit, v)}
            for label, v in METR_THRESHOLDS
            if v > best["value"]
        ],
        "chart": charts.trend_chart(
            pts,
            front,
            fit,
            today,
            thresholds=METR_THRESHOLDS,
            x_end=today + 2.5,
            label="METR 50% time horizon by model release date",
        ),
        "source_url": d["source_url"],
    }


def measured_compute(today: float) -> dict | None:
    d = cached("epoch_compute")
    if not d or not d["points"]:
        return None
    pts = d["points"]
    front = trend.frontier(pts)
    fit = trend.fit_doubling(front, COMPUTE_FIT_START)
    best = trend.best_to_date(pts)
    return {
        "fit": fit,
        "fit_start": COMPUTE_FIT_START,
        "best": best,
        "best_label": f"{best['value']:.1e} FLOP",
        "missing": d["rows_without_compute"],
        "total": d["rows_total"],
        "chart": charts.trend_chart(
            pts,
            front,
            fit,
            today,
            fmt=charts.fmt_flop,
            x_start=2010.0,
            x_end=today + 1.5,
            label="Training compute of frontier AI models by publication date",
        ),
        "source_url": d["source_url"],
    }


def measured_bounded(today: float) -> dict:
    series: dict[str, dict] = {}
    fm = cached("frontiermath")
    if fm and fm["points"]:
        series["FrontierMath T1–3"] = {"points": fm["points"], "reference": []}
    arc = cached("arc")
    if arc:
        for name, s in arc["series"].items():
            if s["points"]:
                series[name] = s
    for s in series.values():
        s["best"] = trend.best_to_date(s["points"])
    # Two series per chart keep the colours distinguishable; ARC-AGI-1 is in the tiles.
    plotted = {k: v for k, v in series.items() if k in ("FrontierMath T1–3", "ARC-AGI-2")}
    chart = charts.bounded_chart(plotted, today, "Best score to date") if plotted else None
    return {"series": series, "chart": chart}


def build_payload(today_d: date) -> dict:
    today = trend.to_year(today_d.isoformat())
    superhuman = curated.load_superhuman()
    all_claims = curated.load_claims()
    # A quote not confirmed at its source stays in the CSV but off the page (SPEC D3).
    claims = [c for c in all_claims if c.get("quote_verified") == "yes"]
    held = len(all_claims) - len(claims)
    events = {e["id"]: e for e in superhuman}
    resolutions = resolve.load_resolutions(set(events), {c["id"] for c in claims})
    qc = cached("quotecheck") or {}
    for c in claims:
        c["status"] = resolve.claim_status(c, today_d, resolutions.get(c["id"]), events)
        c["quotecheck"] = (qc.get("results") or {}).get(c["id"])

    order = ["achieved", "window_open", "open", "passed_unverified", "undated"]
    counts = Counter(c["status"]["status"] for c in claims)
    orgs = Counter(e.get("org_type", "") for e in superhuman)

    payload = {
        "meta": {"generated": datetime.now(UTC).strftime("%Y-%m-%d %H:%M")},
        "counts": {"claims": len(claims), "superhuman": len(superhuman), "held": held},
        "status_counts": {k: counts[k] for k in order if counts[k]},
        "status_labels": resolve.STATUS_LABEL,
        "claims": sorted(claims, key=lambda c: c["date_said"], reverse=True),
        "superhuman": superhuman,
        "org_split": (
            f"Of {len(superhuman)} events, {orgs['industry']} came from industry, "
            f"{orgs['academia']} from academia and {orgs['collaboration']} from collaborations."
        ),
        "quotecheck_at": (qc.get("checked_at") or "")[:10] or None,
        "charts": {
            "promise": charts.promise_horizon(claims, today, "Claims: when said and horizon"),
            "superhuman": charts.superhuman_timeline(superhuman, today, "Superhuman Ledger"),
        },
        "measured": {
            "metr": measured_metr(today),
            "compute": measured_compute(today),
            "bounded": measured_bounded(today),
        },
        "status": cache.status_report(),
    }
    mk = cached("manifold")
    if mk:
        payload["crowd"] = {
            **mk,
            "observed_at": mk["observed_at"][:16].replace("T", " ") + " UTC",
            "chart": charts.crowd_chart(mk["markets"], claims, today, "Crowd vs CEOs"),
        }
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the OVERHANG page.")
    parser.add_argument("--force", action="store_true", help="refresh every source")
    parser.add_argument("--render", action="store_true", help="render from cache; no network")
    args = parser.parse_args()

    # Validate curated data before touching the network, so a bad row fails fast.
    claims = curated.load_claims()
    curated.load_superhuman()
    markets = curated.load_manifold_markets()

    if not args.render:
        f = args.force
        cache.refresh("metr", sources.fetch_metr, force=f)
        cache.refresh("epoch_compute", sources.fetch_epoch_compute, force=f)
        cache.refresh("frontiermath", sources.fetch_frontiermath, force=f)
        cache.refresh("arc", sources.fetch_arc, force=f)
        cache.refresh("manifold", lambda: sources.fetch_manifold(markets), force=f)
        cache.refresh("quotecheck", lambda: quotecheck.fetch(claims), force=f)

    payload = build_payload(datetime.now(UTC).date())

    print("\n=== STATUS ===")
    for name, s in payload["status"].items():
        flag = "STALE" if s["stale"] else "ok   "
        err = f"  last error: {s['last_error']}" if s["last_error"] else ""
        print(f"  {flag} {name:15s} age={s['age']:>6}{err}")
    print(f"  claims by status: {payload['status_counts']}")

    out = ROOT / "docs" / "index.html"
    out.parent.mkdir(exist_ok=True)
    render(payload, out)
    print(f"\nWrote {out.stat().st_size:,} bytes to {out}")


if __name__ == "__main__":
    main()
