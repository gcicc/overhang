"""Frontier envelopes, log-linear fits, doubling times and "if this continues" projections.

The fit is ordinary least squares of log2(value) on time in years, over the frontier
points inside a stated window. The slope is doublings per year, so the doubling time is
1/slope. The window and n are always returned with the estimate, because a doubling time
without its fit window is not a number anyone can check.

Bounded series (benchmark scores in [0, 1]) get no doubling time: a score saturates, so
exponential growth is the wrong model. They report the best score to date and when it
was set.
"""

from __future__ import annotations

import math
from datetime import date


def to_year(d: str) -> float:
    """ISO date string to decimal year."""
    y, m, dd = (int(x) for x in (d[:10] + "-01-01")[:10].split("-"))
    start = date(y, 1, 1).toordinal()
    length = date(y + 1, 1, 1).toordinal() - start
    return y + (date(y, m, dd).toordinal() - start) / length


def from_year(t: float) -> str:
    y = int(math.floor(t))
    start = date(y, 1, 1).toordinal()
    length = date(y + 1, 1, 1).toordinal() - start
    return date.fromordinal(start + int(round((t - y) * length))).isoformat()


def frontier(points: list[dict]) -> list[dict]:
    """Points that set a new record when released (the running maximum), in date order."""
    best = -math.inf
    out = []
    for p in sorted(points, key=lambda p: p["date"]):
        if p["value"] > best:
            best = p["value"]
            out.append(p)
    return out


def fit_doubling(points: list[dict], start: str, end: str | None = None) -> dict | None:
    """OLS of log2(value) on decimal year over points dated in [start, end]."""
    sel = [
        p
        for p in points
        if p["value"] > 0 and p["date"] >= start and (end is None or p["date"] <= end)
    ]
    if len(sel) < 3:
        return None
    xs = [to_year(p["date"]) for p in sel]
    ys = [math.log2(p["value"]) for p in sel]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    ss_res = sum(r * r for r in resid)
    ss_tot = sum((y - my) ** 2 for y in ys)
    if slope <= 0:
        doubling_days = None
    else:
        doubling_days = 365.25 / slope
    return {
        "slope_doublings_per_year": slope,
        "intercept": intercept,
        "doubling_days": doubling_days,
        "growth_per_year": 2**slope,
        "r2": 1 - ss_res / ss_tot if ss_tot else None,
        "n": n,
        "window_start": sel[0]["date"],
        "window_end": sel[-1]["date"],
    }


def predict(fit: dict, t: float) -> float:
    return 2 ** (fit["intercept"] + fit["slope_doublings_per_year"] * t)


def crossing_date(fit: dict, threshold: float) -> str | None:
    """Date the fitted line reaches ``threshold``, if the slope is positive."""
    if not fit or fit["slope_doublings_per_year"] <= 0:
        return None
    t = (math.log2(threshold) - fit["intercept"]) / fit["slope_doublings_per_year"]
    return from_year(t)


def best_to_date(points: list[dict]) -> dict | None:
    if not points:
        return None
    return max(points, key=lambda p: (p["value"], -to_year(p["date"])))
