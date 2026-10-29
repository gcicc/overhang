"""Server-side SVG charts. Deterministic strings, no JS, themed through CSS classes.

Every chart is a ``viewBox`` SVG that scales to its container. Colours come from CSS
custom properties on the page (``var(--...)``), so light and dark themes need no second
render. Text is escaped; labels come from third-party data.
"""

from __future__ import annotations

import math
from html import escape

from overhang.trend import from_year, predict, to_year

W = 760
PAD_L, PAD_R, PAD_T, PAD_B = 64, 20, 18, 34


def _svg(height: int, body: list[str], label: str) -> str:
    return (
        f'<svg class="chart" viewBox="0 0 {W} {height}" role="img" '
        f'aria-label="{escape(label)}" preserveAspectRatio="xMidYMid meet">'
        + "".join(body)
        + "</svg>"
    )


class Scale:
    def __init__(self, d0: float, d1: float, r0: float, r1: float, log: bool = False):
        self.log = log
        self.d0, self.d1 = (math.log10(d0), math.log10(d1)) if log else (d0, d1)
        self.r0, self.r1 = r0, r1

    def __call__(self, v: float) -> float:
        v = math.log10(v) if self.log else v
        return self.r0 + (v - self.d0) / (self.d1 - self.d0) * (self.r1 - self.r0)


def _year_ticks(x: Scale, y0: float, y1: float, top: float, bottom: float, step: int) -> list[str]:
    out = []
    first = int(math.ceil(y0 / step) * step)
    for yr in range(first, int(y1) + 1, step):
        px = x(yr)
        out.append(f'<line class="grid" x1="{px:.1f}" x2="{px:.1f}" y1="{top}" y2="{bottom}"/>')
        out.append(
            f'<text class="tick" x="{px:.1f}" y="{bottom + 16}" text-anchor="middle">{yr}</text>'
        )
    return out


def _today_line(x: Scale, today: float, top: float, bottom: float) -> list[str]:
    px = x(today)
    return [
        f'<line class="now" x1="{px:.1f}" x2="{px:.1f}" y1="{top}" y2="{bottom}"/>',
        f'<text class="now-label" x="{px + 4:.1f}" y="{top + 10}">now</text>',
    ]


def fmt_minutes(m: float) -> str:
    if m < 1:
        return f"{m * 60:.0f} s"
    if m < 60:
        return f"{m:.0f} min"
    if m < 60 * 24:
        return f"{m / 60:.0f} h"
    return f"{m / 60 / 8 / 5:.0f} wk"


def fmt_flop(v: float) -> str:
    return f"1e{math.log10(v):.0f}"


def trend_chart(
    points: list[dict],
    front: list[dict],
    fit: dict | None,
    today: float,
    *,
    fmt=fmt_minutes,
    thresholds: tuple[tuple[str, float], ...] = (),
    x_start: float | None = None,
    x_end: float | None = None,
    label: str = "trend",
) -> str:
    """Log-scale scatter: all points faint, frontier points solid, fit line projected.

    ``x_start`` crops the plotted range (points before it are not drawn); the fit is
    computed by the caller and is unaffected.
    """
    h = 300
    top, bottom = PAD_T, h - PAD_B
    if x_start is not None:
        points = [p for p in points if to_year(p["date"]) >= x_start]
    xs = [to_year(p["date"]) for p in points]
    x0 = math.floor(min(xs))
    x1 = x_end or math.ceil(max(xs + [today])) + 0.5
    vals = [p["value"] for p in points if p["value"] > 0] + [v for _, v in thresholds]
    y0 = 10 ** math.floor(math.log10(min(vals)))
    y1 = 10 ** math.ceil(math.log10(max(vals)))
    x = Scale(x0, x1, PAD_L, W - PAD_R)
    y = Scale(y0, y1, bottom, top, log=True)
    span = x1 - x0
    body = _year_ticks(x, x0, x1, top, bottom, 1 if span <= 10 else 2 if span <= 20 else 5)
    decades = int(math.log10(y1)) - int(math.log10(y0))
    every = 1 if decades <= 9 else 2 if decades <= 18 else 3
    exp = int(math.log10(y0))
    while 10**exp <= y1:
        py = y(10**exp)
        if (exp - int(math.log10(y0))) % every:
            exp += 1
            continue
        body.append(
            f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
        )
        body.append(
            f'<text class="tick" x="{PAD_L - 6}" y="{py + 4:.1f}" text-anchor="end">'
            f"{escape(fmt(10**exp))}</text>"
        )
        exp += 1
    for name, v in thresholds:
        py = y(v)
        body.append(
            f'<line class="threshold" x1="{PAD_L}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
        )
        body.append(
            f'<text class="threshold-label" x="{W - PAD_R - 4}" y="{py - 4:.1f}" text-anchor="end">{escape(name)}</text>'
        )
    if fit:
        a = to_year(fit["window_start"])
        b = to_year(fit["window_end"])
        body.append(
            f'<line class="fit" x1="{x(a):.1f}" y1="{y(predict(fit, a)):.1f}" '
            f'x2="{x(b):.1f}" y2="{y(predict(fit, b)):.1f}"/>'
        )
        # Projection: from the end of the fit window to the chart edge or the top, whichever first.
        end = x1
        if predict(fit, end) > y1:
            end = (math.log2(y1) - fit["intercept"]) / fit["slope_doublings_per_year"]
        if end > b:
            body.append(
                f'<line class="projection" x1="{x(b):.1f}" y1="{y(predict(fit, b)):.1f}" '
                f'x2="{x(end):.1f}" y2="{y(predict(fit, end)):.1f}"/>'
            )
    body += _today_line(x, today, top, bottom)
    front_ids = {id(p) for p in front}
    for p in points:
        if p["value"] <= 0:
            continue
        cls = "pt-front" if id(p) in front_ids else "pt"
        tip = f"{p['model']} · {p['date']} · {fmt(p['value'])}"
        body.append(
            f'<circle class="{cls}" cx="{x(to_year(p["date"])):.1f}" cy="{y(p["value"]):.1f}" '
            f'r="{4 if cls == "pt-front" else 2.5}"><title>{escape(tip)}</title></circle>'
        )
    return _svg(h, body, label)


def bounded_chart(series: dict[str, dict], today: float, label: str) -> str:
    """Linear 0-100% chart: one stepped best-to-date line per series, points faint."""
    h = 260
    top, bottom = PAD_T, h - PAD_B
    all_pts = [p for s in series.values() for p in s["points"]]
    x0 = math.floor(min(to_year(p["date"]) for p in all_pts))
    x1 = math.ceil(today) + 0.25
    x = Scale(x0, x1, PAD_L, W - PAD_R)
    y = Scale(0, 1, bottom, top)
    body = _year_ticks(x, x0, x1, top, bottom, 1)
    for v in (0, 0.25, 0.5, 0.75, 1):
        py = y(v)
        body.append(
            f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
        )
        body.append(
            f'<text class="tick" x="{PAD_L - 6}" y="{py + 4:.1f}" text-anchor="end">{v:.0%}</text>'
        )
    for i, (name, s) in enumerate(series.items()):
        for ref in s.get("reference", []):
            py = y(min(ref["value"], 1))
            body.append(
                f'<line class="threshold" x1="{PAD_L}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
            )
            body.append(
                f'<text class="threshold-label" x="{PAD_L + 4}" y="{py - 4:.1f}">'
                f"{escape(name)}: {escape(ref['label'])} {ref['value']:.0%}</text>"
            )
        for p in s["points"]:
            body.append(
                f'<circle class="pt s{i}" cx="{x(to_year(p["date"])):.1f}" cy="{y(p["value"]):.1f}" r="2.5">'
                f"<title>{escape(name)} · {escape(p['model'])} · {p['date']} · {p['value']:.0%}</title></circle>"
            )
        best, path = 0.0, []
        for p in sorted(s["points"], key=lambda p: p["date"]):
            if p["value"] > best:
                px = x(to_year(p["date"]))
                if path:
                    path.append(f"L{px:.1f},{y(best):.1f}")
                best = p["value"]
                path.append(f"{'L' if path else 'M'}{px:.1f},{y(best):.1f}")
        if path:
            path.append(f"L{x(today):.1f},{y(best):.1f}")
            body.append(f'<path class="step s{i}" d="{" ".join(path)}"/>')
            body.append(
                f'<text class="series-label s{i}" x="{x(today) + 4:.1f}" y="{y(best) + 4:.1f}">'
                f"{escape(name)}</text>"
            )
    nx = x(today)
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top}" y2="{bottom}"/>')
    body.append(
        f'<text class="now-label" x="{nx - 4:.1f}" y="{bottom - 6}" text-anchor="end">now</text>'
    )
    return _svg(h, body, label)


STATUS_CLASS = {
    "achieved": "st-achieved",
    "undated": "st-undated",
    "open": "st-open",
    "window_open": "st-window",
    "passed_unverified": "st-passed",
}


def promise_horizon(claims: list[dict], today: float, label: str) -> str:
    """One row per claim: a dot when it was said, a bar over the horizon window.

    The x axis is piecewise linear with a break at 2015: 1945-2015 takes 35% of the
    width and 2015-2065 takes 65%, so the dense recent claims get room. The break is
    marked on the chart. An achieved claim gets a diamond at the evidence date.
    """
    origin, brk, end = 1945.0, 2015.0, 2065.0
    share = 0.35

    def tx(v: float) -> float:
        v = min(max(v, origin), end)
        if v <= brk:
            return share * (v - origin) / (brk - origin)
        return share + (1 - share) * (v - brk) / (end - brk)

    rows = sorted(claims, key=lambda c: (c["date_said"], c["id"]))
    row_h = 15
    top = PAD_T + 16
    h = top + row_h * len(rows) + PAD_B
    left = 210
    x = Scale(0, 1, left, W - PAD_R)
    body = []
    for yr in (1950, 1970, 1990, 2010, 2020, 2030, 2040, 2050, 2060):
        px = x(tx(yr))
        body.append(
            f'<line class="grid" x1="{px:.1f}" x2="{px:.1f}" y1="{top - 4}" y2="{h - PAD_B}"/>'
        )
        body.append(
            f'<text class="tick" x="{px:.1f}" y="{h - PAD_B + 16}" text-anchor="middle">{yr}</text>'
        )
        body.append(
            f'<text class="tick" x="{px:.1f}" y="{top - 8}" text-anchor="middle">{yr}</text>'
        )
    bx = x(tx(brk))
    body.append(
        f'<line class="axis-break" x1="{bx:.1f}" x2="{bx:.1f}" y1="{top - 4}" y2="{h - PAD_B}"/>'
    )
    nx = x(tx(today))
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top - 4}" y2="{h - PAD_B}"/>')
    body.append(f'<text class="now-label" x="{nx + 4:.1f}" y="{h - PAD_B - 4}">now</text>')
    for i, c in enumerate(rows):
        cy = top + i * row_h + row_h / 2
        st = c["status"]["status"]
        cls = STATUS_CLASS[st]
        said = to_year(c["date_said"])
        name = c["speaker"] if len(c["speaker"]) <= 30 else c["speaker"][:29] + "…"
        body.append(
            f'<a href="#{escape(c["id"])}"><text class="row-label" x="{left - 8}" y="{cy + 4:.1f}" '
            f'text-anchor="end">{escape(name)} · {c["date_said"][:4]}</text></a>'
        )
        tip = f"{c['speaker']} ({c['date_said']}): {c['claim_summary']} — {c['status']['label']}"
        if c.get("horizon_lo"):
            lo, hi = to_year(c["horizon_lo"]), to_year(c["horizon_hi"]) + 1 / 365
            body.append(
                f'<line class="said-link" x1="{x(tx(said)):.1f}" x2="{x(tx(lo)):.1f}" '
                f'y1="{cy:.1f}" y2="{cy:.1f}"/>'
            )
            body.append(
                f'<rect class="window {cls}" x="{x(tx(lo)):.1f}" y="{cy - 4:.1f}" '
                f'width="{max(x(tx(hi)) - x(tx(lo)), 3):.1f}" height="8" rx="2">'
                f"<title>{escape(tip)}</title></rect>"
            )
        body.append(
            f'<circle class="said" cx="{x(tx(said)):.1f}" cy="{cy:.1f}" r="3">'
            f"<title>{escape(tip)}</title></circle>"
        )
        ev = c["status"].get("evidence")
        if ev:
            ex = x(tx(to_year(ev["date"])))
            body.append(
                f'<path class="evidence" d="M{ex:.1f},{cy - 5:.1f} l5,5 l-5,5 l-5,-5 z">'
                f"<title>{escape(ev['achievement'])} ({ev['date']})</title></path>"
            )
    return _svg(h, body, label)


LEVEL_CLASS = {
    "exceeded_best": "lv-exceeded",
    "matched_best": "lv-matched",
    "exceeded_expert_median": "lv-expert",
    "contested": "lv-contested",
}


def superhuman_timeline(events: list[dict], today: float, label: str) -> str:
    """Dot plot by domain lane. Filled by level; hollow when confidence is low."""
    domains: list[str] = []
    for e in events:
        if e["domain"] not in domains:
            domains.append(e["domain"])
    lane_h = 30
    top = PAD_T + 6
    h = top + lane_h * len(domains) + PAD_B
    left = 120
    x0, x1 = 1990, math.ceil(today) + 1
    x = Scale(x0, x1, left, W - PAD_R)
    body = _year_ticks(x, x0, x1, top - 6, h - PAD_B, 5)
    nx = x(today)
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top - 6}" y2="{h - PAD_B}"/>')
    lane_y = {}
    for i, d in enumerate(domains):
        cy = top + i * lane_h + lane_h / 2
        lane_y[d] = cy
        body.append(
            f'<line class="lane" x1="{left}" x2="{W - PAD_R}" y1="{cy:.1f}" y2="{cy:.1f}"/>'
        )
        body.append(
            f'<text class="row-label" x="{left - 8}" y="{cy + 4:.1f}" text-anchor="end">{escape(d)}</text>'
        )
    stacked: dict[tuple[str, int], int] = {}
    for e in events:
        t = to_year(e["date"])
        key = (e["domain"], int(t))
        k = stacked.get(key, 0)
        stacked[key] = k + 1
        cy = lane_y[e["domain"]] + (k % 3 - 1) * 7 if k else lane_y[e["domain"]]
        cls = LEVEL_CLASS[e["level"]] + (" low" if e["confidence"] == "low" else "")
        tip = f"{e['date']} · {e['achievement']} · {e['level'].replace('_', ' ')} · {e['confidence']} confidence"
        body.append(
            f'<a href="#{escape(e["id"])}"><circle class="sh {cls}" cx="{x(t):.1f}" cy="{cy:.1f}" r="5">'
            f"<title>{escape(tip)}</title></circle></a>"
        )
    return _svg(h, body, label)


def crowd_chart(markets: list[dict], claims: list[dict], today: float, label: str) -> str:
    """Market-implied P(AGI before year) above; one row per dated CEO horizon below."""
    pts = sorted((m for m in markets if m.get("probability") is not None), key=lambda m: m["year"])
    x0, x1 = math.floor(today), 2036
    rows = sorted(
        (
            c
            for c in claims
            if c["set"] == "current" and c.get("horizon_lo") and to_year(c["horizon_lo"]) <= x1
        ),
        key=lambda c: (c["horizon_lo"], c["horizon_hi"]),
    )
    top, chart_bottom = PAD_T, 190
    row_h = 14
    rows_top = chart_bottom + 22
    h = rows_top + row_h * len(rows) + PAD_B
    left = 170
    x = Scale(x0, x1, left, W - PAD_R)
    y = Scale(0, 1, chart_bottom, top)
    body = _year_ticks(x, x0, x1, top, h - PAD_B, 1)
    for v in (0, 0.25, 0.5, 0.75, 1):
        py = y(v)
        body.append(
            f'<line class="grid" x1="{left}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
        )
        body.append(
            f'<text class="tick" x="{left - 6}" y="{py + 4:.1f}" text-anchor="end">{v:.0%}</text>'
        )
    body.append(
        f'<text class="row-label" x="{left - 40}" y="{y(0.5) + 4:.1f}" text-anchor="end">'
        "P(AGI before year)</text>"
    )
    if pts:
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{x(m['year']):.1f},{y(m['probability']):.1f}"
            for i, m in enumerate(pts)
        )
        body.append(f'<path class="crowd" d="{d}"/>')
        for m in pts:
            body.append(
                f'<circle class="pt-front" cx="{x(m["year"]):.1f}" '
                f'cy="{y(m["probability"]):.1f}" r="4">'
                f"<title>{escape(m['question'])}: {m['probability']:.0%}</title></circle>"
            )
    for i, c in enumerate(rows):
        cy = rows_top + i * row_h + row_h / 2
        lo = to_year(c["horizon_lo"])
        hi = min(to_year(c["horizon_hi"]) + 1 / 365, x1)
        cls = STATUS_CLASS[c["status"]["status"]]
        body.append(
            f'<a href="#{escape(c["id"])}"><text class="row-label" x="{left - 6}" '
            f'y="{cy + 4:.1f}" text-anchor="end">{escape(c["speaker"])} · '
            f"{c['date_said'][:4]}</text></a>"
        )
        tip = f"<title>{escape(c['speaker'])}: {escape(c['claim_summary'])}</title>"
        if hi < x0:
            # The whole window ended before the axis starts: say when, don't pin it to x0.
            body.append(
                f'<text class="row-label {cls}-text" x="{x(x0) + 2:.1f}" y="{cy + 4:.1f}">'
                f"◂ {c['horizon_hi'][:7]}{tip}</text>"
            )
            continue
        body.append(
            f'<rect class="window {cls}" x="{x(max(lo, x0)):.1f}" y="{cy - 4:.1f}" '
            f'width="{max(x(hi) - x(max(lo, x0)), 3):.1f}" height="8" rx="2">{tip}</rect>'
        )
    nx = x(today)
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top}" y2="{h - PAD_B}"/>')
    body.append(f'<text class="now-label" x="{nx + 4:.1f}" y="{top + 10}">now</text>')
    return _svg(h, body, label)


# --- The Race and Compute & Silicon ---------------------------------------
# Categorical colour classes are ``c1``..``c7`` (fixed slot per entity, see race.SLOTS)
# and ``c0`` for anything unlisted. Colour never carries identity alone: every segment
# wide enough is labelled, every mark has a tooltip, and each chart has a table nearby.


def _short(org: str, n: int = 10) -> str:
    return org if len(org) <= n else org[: max(n - 1, 1)] + "…"


def ribbon_chart(rows: list[dict], x0: float, today: float, slot_of, label: str) -> str:
    """One horizontal band per metric, split into holder spells coloured by organisation."""
    row_h, gap = 26, 10
    left = 150
    top = PAD_T + 4
    h = top + len(rows) * (row_h + gap) + PAD_B - gap
    x = Scale(x0, today, left, W - PAD_R)
    body = _year_ticks(x, x0, today, top - 4, h - PAD_B, 1)
    for i, r in enumerate(rows):
        y = top + i * (row_h + gap)
        body.append(
            f'<text class="row-label" x="{left - 8}" y="{y + row_h / 2 + 4:.1f}" '
            f'text-anchor="end">{escape(r["name"])}</text>'
        )
        for s in r["spells"]:
            a, b = x(to_year(s["start"])), x(to_year(s["end"]))
            w = max(b - a - 2, 1)  # 2px surface gap between adjacent spells
            end = "now" if s.get("ongoing") else s["end"]
            tip = (
                f"{r['name']} · {s['org']} held #1 {s['start']} → {end} "
                f"({s['days']} days) · {s['model']}"
            )
            body.append(
                f'<rect class="spell c{slot_of(s["org"])}" x="{a:.1f}" y="{y}" '
                f'width="{w:.1f}" height="{row_h}" rx="3"><title>{escape(tip)}</title></rect>'
            )
            if w > 46:
                body.append(
                    f'<text class="spell-label" x="{a + 5:.1f}" y="{y + row_h / 2 + 4:.1f}">'
                    f"{escape(_short(s['org'], int(w / 7)))}</text>"
                )
    nx = x(today)
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top - 4}" y2="{h - PAD_B}"/>')
    return _svg(h, body, label)


def hbar_chart(rows: list[tuple[str, float, str]], fmt, label: str) -> str:
    """Single-series horizontal bars: (name, value, tooltip). Value labels at bar ends."""
    bar_h, gap = 16, 6
    left = 130
    top = PAD_T
    h = top + len(rows) * (bar_h + gap) + 10
    vmax = max(v for _, v, _ in rows) or 1
    x = Scale(0, vmax, left, W - PAD_R - 70)
    body = []
    for i, (name, v, tip) in enumerate(rows):
        y = top + i * (bar_h + gap)
        body.append(
            f'<text class="row-label" x="{left - 8}" y="{y + bar_h / 2 + 4:.1f}" '
            f'text-anchor="end">{escape(name)}</text>'
        )
        body.append(
            f'<rect class="bar" x="{left}" y="{y}" width="{max(x(v) - left, 1):.1f}" '
            f'height="{bar_h}" rx="3"><title>{escape(tip)}</title></rect>'
        )
        body.append(
            f'<text class="tick" x="{max(x(v), left) + 6:.1f}" y="{y + bar_h / 2 + 4:.1f}">'
            f"{escape(fmt(v))}</text>"
        )
    return _svg(h, body, label)


def lines_chart(
    series: dict[str, dict], today: float, *, fmt, log: bool, label: str, x0: float | None = None
) -> str:
    """Multi-line chart, one y axis. ``series[name] = {"points": [(t, v)], "slot": int}``.

    Each line is direct-labelled at its end, so identity never rests on colour.
    """
    h = 280
    top, bottom = PAD_T, h - PAD_B
    right = W - PAD_R - 84
    pts = [(t, v) for s in series.values() for t, v in s["points"] if v > 0]
    if x0 is None:
        x0 = math.floor(min(t for t, _ in pts))
    pts = [(t, v) for t, v in pts if t >= x0]
    x1 = max(today, max(t for t, _ in pts))
    vals = [v for _, v in pts]
    if log:
        y0 = 10 ** math.floor(math.log10(min(vals)))
        y1 = 10 ** math.ceil(math.log10(max(vals)))
        ticks = [10**e for e in range(round(math.log10(y0)), round(math.log10(y1)) + 1)]
    else:
        y0, y1 = 0.0, max(vals) * 1.08
        step = 10 ** math.floor(math.log10(y1 / 4))
        while y1 / step > 8:
            step *= 2
        ticks = [step * k for k in range(int(y1 / step) + 1)]
    x = Scale(x0, x1, PAD_L, right)
    y = Scale(y0, y1, bottom, top, log=log)
    body = _year_ticks(x, x0, x1, top, bottom, 1)
    for v in ticks:
        py = y(v)
        body.append(f'<line class="grid" x1="{PAD_L}" x2="{right}" y1="{py:.1f}" y2="{py:.1f}"/>')
        body.append(
            f'<text class="tick" x="{PAD_L - 6}" y="{py + 4:.1f}" text-anchor="end">'
            f"{escape(fmt(v))}</text>"
        )
    ends = []
    for name, s in series.items():
        line = [(t, v) for t, v in s["points"] if v > 0 and t >= x0]
        if not line:
            continue
        d = " ".join(
            f"{'M' if i == 0 else 'L'}{x(t):.1f},{y(v):.1f}" for i, (t, v) in enumerate(line)
        )
        body.append(f'<path class="line c{s["slot"]}" d="{d}"/>')
        for t, v in line:
            body.append(
                f'<circle class="hit" cx="{x(t):.1f}" cy="{y(v):.1f}" r="5">'
                f"<title>{escape(name)} · {from_year(t)} · {escape(fmt(v))}</title></circle>"
            )
        ends.append([y(line[-1][1]), name, s["slot"]])
    # Nudge end labels apart so they never overlap.
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 13)
    for py, name, sl in ends:
        body.append(
            f'<text class="end-label" x="{right + 6}" y="{py + 4:.1f}">'
            f'<tspan class="swatch c{sl}">■</tspan> {escape(name)}</text>'
        )
    return _svg(h, body, label)


def category_scatter(
    points: list[dict], fit: dict | None, today: float, slot_of, *, fmt, label: str, x0: float
) -> str:
    """Log-scale scatter coloured by ``org`` slot, optional fit line over its window."""
    h = 300
    top, bottom = PAD_T, h - PAD_B
    pts = [p for p in points if p["value"] > 0 and to_year(p["date"]) >= x0]
    x1 = math.ceil(today) + 0.25
    y0 = 10 ** math.floor(math.log10(min(p["value"] for p in pts)))
    y1 = 10 ** math.ceil(math.log10(max(p["value"] for p in pts)))
    x = Scale(x0, x1, PAD_L, W - PAD_R)
    y = Scale(y0, y1, bottom, top, log=True)
    body = _year_ticks(x, x0, x1, top, bottom, 1 if x1 - x0 <= 12 else 2)
    for e in range(round(math.log10(y0)), round(math.log10(y1)) + 1):
        py = y(10**e)
        body.append(
            f'<line class="grid" x1="{PAD_L}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
        )
        body.append(
            f'<text class="tick" x="{PAD_L - 6}" y="{py + 4:.1f}" text-anchor="end">'
            f"{escape(fmt(10**e))}</text>"
        )
    if fit:
        a, b = to_year(fit["window_start"]), to_year(fit["window_end"])
        body.append(
            f'<line class="fit" x1="{x(a):.1f}" y1="{y(predict(fit, a)):.1f}" '
            f'x2="{x(b):.1f}" y2="{y(predict(fit, b)):.1f}"/>'
        )
    body += _today_line(x, today, top, bottom)
    for p in pts:
        tip = f"{p['model']} · {p['org']} · {p['date']} · {fmt(p['value'])}"
        body.append(
            f'<circle class="cat c{slot_of(p["org"])}" cx="{x(to_year(p["date"])):.1f}" '
            f'cy="{y(p["value"]):.1f}" r="4"><title>{escape(tip)}</title></circle>'
        )
    return _svg(h, body, label)


SECTOR_SLOT = {"academia": 7, "industry": 4, "both": 3, "other": 0}
HISTORY_LANES = [
    ("academia", "Academia"),
    ("industry", "Industry"),
    ("government", "Government"),
    ("superhuman", "Superhuman firsts"),
]


def history_timeline(
    notable: list[dict], history: list[dict], superhuman: list[dict], today: float, label: str
) -> str:
    """One time axis from 1940: model compute above, milestone lanes below, winters shaded.

    The x axis is piecewise linear with a marked break at 2010 (1940-2010 takes 45% of the
    width) so the dense recent decade is readable. Compute dots are coloured by sector;
    milestones and superhuman firsts stay in ink so they never borrow a sector colour.
    """
    origin, brk, end = 1940.0, 2010.0, math.ceil(today) + 0.5
    share = 0.45
    left = 118

    def tx(v: float) -> float:
        v = min(max(v, origin), end)
        if v <= brk:
            return share * (v - origin) / (brk - origin)
        return share + (1 - share) * (v - brk) / (end - brk)

    x = Scale(0, 1, left, W - PAD_R)
    top, chart_bottom = PAD_T + 14, 250
    lane_h = 26
    lanes_top = chart_bottom + 14
    bottom = lanes_top + lane_h * len(HISTORY_LANES)
    h = bottom + PAD_B
    body: list[str] = []
    for w in (r for r in history if r["lane"] == "winter"):
        a, b = x(tx(to_year(w["date"]))), x(tx(to_year(w["date_end"]) + 1))
        tip = f"{w['title']}, about {w['date']}–{w['date_end']}"
        body.append(
            f'<rect class="winter" x="{a:.1f}" y="{top - 14}" width="{b - a:.1f}" '
            f'height="{bottom - top + 14}"><title>{escape(tip)}</title></rect>'
        )
        body.append(
            f'<text class="winter-label" x="{(a + b) / 2:.1f}" y="{top - 4}" '
            f'text-anchor="middle">AI winter</text>'
        )
    for yr in (1940, 1950, 1960, 1970, 1980, 1990, 2000, 2010, 2015, 2020, 2025):
        if yr > end:
            continue
        px = x(tx(yr))
        body.append(f'<line class="grid" x1="{px:.1f}" x2="{px:.1f}" y1="{top}" y2="{bottom}"/>')
        body.append(
            f'<text class="tick" x="{px:.1f}" y="{bottom + 16}" text-anchor="middle">{yr}</text>'
        )
    bx = x(tx(brk))
    body.append(f'<line class="axis-break" x1="{bx:.1f}" x2="{bx:.1f}" y1="{top}" y2="{bottom}"/>')
    pts = [p for p in notable if p["value"] > 0]
    if pts:
        y0 = 10 ** math.floor(math.log10(min(p["value"] for p in pts)))
        y1 = 10 ** math.ceil(math.log10(max(p["value"] for p in pts)))
        y = Scale(y0, y1, chart_bottom, top, log=True)
        lo, hi = round(math.log10(y0)), round(math.log10(y1))
        for e in range(lo + (-lo) % 5, hi + 1, 5):
            py = y(10**e)
            body.append(
                f'<line class="grid" x1="{left}" x2="{W - PAD_R}" y1="{py:.1f}" y2="{py:.1f}"/>'
            )
            body.append(
                f'<text class="tick" x="{left - 6}" y="{py + 4:.1f}" text-anchor="end">'
                f"{fmt_flop(10**e)}</text>"
            )
        body.append(
            f'<text class="row-label" x="{left - 6}" y="{top - 4}" text-anchor="end">'
            "Training FLOP</text>"
        )
        for p in pts:
            tip = f"{p['model']} · {p['org'] or 'organisation not stated'} · {p['date']} · {fmt_flop(p['value'])} FLOP"
            body.append(
                f'<circle class="cat c{SECTOR_SLOT[p["sector"]]}" '
                f'cx="{x(tx(to_year(p["date"]))):.1f}" cy="{y(p["value"]):.1f}" r="3">'
                f"<title>{escape(tip)}</title></circle>"
            )
    lane_y = {}
    for i, (key, name) in enumerate(HISTORY_LANES):
        cy = lanes_top + i * lane_h + lane_h / 2
        lane_y[key] = cy
        body.append(
            f'<line class="lane" x1="{left}" x2="{W - PAD_R}" y1="{cy:.1f}" y2="{cy:.1f}"/>'
        )
        body.append(
            f'<text class="row-label" x="{left - 8}" y="{cy + 4:.1f}" text-anchor="end">{name}</text>'
        )
    last_x: dict[str, tuple[float, int]] = {}

    def nudge(lane: str, px: float) -> float:
        prev = last_x.get(lane)
        k = (prev[1] + 1) % 3 if prev and px - prev[0] < 7 else 0
        last_x[lane] = (px, k)
        return lane_y[lane] + (0, -7, 7)[k]

    marks = [
        (to_year(r["date"]), r["lane"], r, False) for r in history if r["lane"] != "winter"
    ] + [(to_year(e["date"]), "superhuman", e, True) for e in superhuman]
    for t, lane, r, lv in sorted(marks, key=lambda m: (m[1], m[0])):
        px = x(tx(t))
        cy = nudge(lane, px)
        if lv:
            cls = "ms-first"
            tip = f"{r['date']} · {r['achievement']} · {r['level'].replace('_', ' ')}"
        else:
            cls = "ms"
            tip = f"{r['date']} · {r['title']}" + (f" · {r['who']}" if r.get("who") else "")
        body.append(
            f'<a href="#{escape(r["id"])}"><circle class="{cls}" cx="{px:.1f}" cy="{cy:.1f}" '
            f'r="4.5"><title>{escape(tip)}</title></circle></a>'
        )
    nx = x(tx(today))
    body.append(f'<line class="now" x1="{nx:.1f}" x2="{nx:.1f}" y1="{top}" y2="{bottom}"/>')
    return _svg(h, body, label)
