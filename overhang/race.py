"""The Race: who held the frontier on each measured axis, when, and for how long.

For one metric, the holder on a given day is the organisation whose model has the best
value released on or before that day. A *spell* is an unbroken run of days held by one
organisation; a new record by the holder extends its spell rather than starting one.
Ties keep the earlier holder: matching a record is not taking the lead.

Tenure statistics are over *completed* spells. The current spell is still running, so
its length is a lower bound and is reported separately, not mixed into the median.

Everything here is computed from the measured series. Nothing is curated except the
organisation aliases below, which only merge names that refer to the same lab.
"""

from __future__ import annotations

import statistics
from datetime import date

# Names that refer to one lab. DeepMind and Google Brain merged into Google DeepMind
# in April 2023; earlier rows are folded in so the Google line is continuous.
ORG_ALIASES = {
    "Google DeepMind": "Google",
    "DeepMind": "Google",
    "Google Brain": "Google",
    "Google Research": "Google",
    "Meta AI": "Meta",
    "Facebook AI Research": "Meta",
    "Facebook": "Meta",
    "Z.ai (Zhipu AI)": "Zhipu",
    "Z.ai": "Zhipu",
    "Moonshot AI": "Moonshot",
    "Mistral AI": "Mistral",
    "NVIDIA": "Nvidia",
    "Kunlunxin Baidu": "Baidu",
    "Amazon AWS": "Amazon",
}

# Fixed colour slot per entity (dataviz rule: colour follows the entity, never its
# rank). Anything unlisted is drawn neutral grey and named in its label.
SLOTS = {
    "OpenAI": 1,
    "Anthropic": 2,
    "Google": 3,
    "xAI": 4,
    "Meta": 5,
    "DeepSeek": 6,
    "Alibaba": 7,
    # Hardware vendors reuse slots on their own chart; Google keeps slot 3 on both.
    "Nvidia": 1,
    "AMD": 2,
    "Huawei": 4,
    # Companies on the filings and price charts. Alphabet shares Google's slot.
    "Alphabet": 3,
    "Amazon": 4,
    "Broadcom": 6,
    "Microsoft": 7,
    "TSMC": 7,
}


def normalise_org(raw: str | None) -> str:
    """First listed organisation, with aliases merged. Empty becomes "Unknown"."""
    first = (raw or "").split(",")[0].strip()
    return ORG_ALIASES.get(first, first) or "Unknown"


def slot(org: str) -> int:
    """Colour slot for a raw or normalised organisation name; 0 means "other"."""
    return SLOTS.get(normalise_org(org), 0)


def spells(points: list[dict], today: str, start: str | None = None) -> list[dict]:
    """Holder spells for one metric, clipped to [start, today].

    ``points`` need ``date``, ``value``, ``org`` and ``model``. The holder entering the
    window keeps its spell from ``start``, so the first spell is not truncated to the
    first record set inside it.
    """
    best = None
    out: list[dict] = []
    for p in sorted(points, key=lambda p: (p["date"][:10], -p["value"])):
        if p["date"][:10] > today:
            continue
        if best is not None and p["value"] <= best:
            continue
        best = p["value"]
        org = normalise_org(p.get("org"))
        if out and out[-1]["org"] == org:
            out[-1].update(model=p["model"], value=p["value"], records=out[-1]["records"] + 1)
            continue
        out.append(
            {
                "org": org,
                "start": p["date"][:10],
                "model": p["model"],
                "value": p["value"],
                "records": 1,
            }
        )
    for a, b in zip(out, out[1:]):
        a["end"] = b["start"]
    if out:
        out[-1]["end"] = today
        out[-1]["ongoing"] = True
    if start:
        out = [s for s in out if s["end"] > start]
        if out and out[0]["start"] < start:
            out[0] = {**out[0], "start": start, "clipped": True}
    for s in out:
        s["days"] = _days(s["start"], s["end"])
    return out


def tenure(sp: list[dict]) -> dict:
    """Days at #1 per organisation, lead changes, and completed-spell tenure."""
    days: dict[str, int] = {}
    for s in sp:
        days[s["org"]] = days.get(s["org"], 0) + s["days"]
    # A spell clipped at the window start is censored on the left; leave it out too.
    completed = [s["days"] for s in sp if not s.get("ongoing") and not s.get("clipped")]
    recent = completed[-5:]
    current = sp[-1] if sp else None
    return {
        "days_by_org": dict(sorted(days.items(), key=lambda kv: -kv[1])),
        "lead_changes": max(len(sp) - 1, 0),
        "completed_n": len(completed),
        "median_tenure_days": statistics.median(completed) if completed else None,
        "recent_median_days": statistics.median(recent) if len(recent) >= 3 else None,
        "current": current,
    }


def country_share(points: list[dict], since_year: int) -> dict:
    """Frontier models per country group per year, fractional for multi-country rows.

    "United States of America,United States of America" is one country, not two; a
    genuinely joint row splits its single model evenly across the countries listed.
    """
    groups = {"United States of America": "US", "China": "China"}
    by_year: dict[int, dict[str, float]] = {}
    for p in points:
        year = int(p["date"][:4])
        if year < since_year:
            continue
        names = sorted({c.strip() for c in (p.get("country") or "").split(",") if c.strip()})
        if not names:
            names = ["Unknown"]
        row = by_year.setdefault(year, {"US": 0.0, "China": 0.0, "Other": 0.0})
        for c in names:
            row[groups.get(c, "Other")] += 1 / len(names)
    totals = {"US": 0.0, "China": 0.0, "Other": 0.0}
    for row in by_year.values():
        for k, v in row.items():
            totals[k] += v
    return {
        "by_year": dict(sorted(by_year.items())),
        "totals": totals,
        "n": round(sum(totals.values())),
    }


def _days(a: str, b: str) -> int:
    return (date.fromisoformat(b) - date.fromisoformat(a)).days
