"""Load and validate the hand-curated ledgers in ``data/curated/``.

These files are the part of the site a person writes, so they are checked hardest. Any
row without a source URL, with an unparseable date, or with an out-of-vocabulary
grade fails the build (SPEC D2). An invalid row is never silently skipped, because a
dropped row is an editorial decision nobody made.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

CURATED = Path(__file__).resolve().parent.parent / "data" / "curated"

SUPERHUMAN_LEVELS = {"matched_best", "exceeded_best", "exceeded_expert_median", "contested"}
CONFIDENCE = {"high", "medium", "low"}
CLAIM_SETS = {"graveyard", "current"}
DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")


class CuratedError(ValueError):
    """A curated row fails validation; the message names the file, row id and field."""


def _read(name: str) -> list[dict]:
    path = CURATED / name
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _require(row: dict, fields: list[str], where: str) -> None:
    for f in fields:
        if not (row.get(f) or "").strip():
            raise CuratedError(f"{where}: missing {f}")
    url = row["source_url"].strip()
    if not url.startswith(("http://", "https://")):
        raise CuratedError(f"{where}: source_url is not a URL: {url!r}")


def load_superhuman() -> list[dict]:
    rows = _read("superhuman.csv")
    seen: set[str] = set()
    for r in rows:
        where = f"superhuman.csv[{r.get('id')}]"
        _require(
            r,
            [
                "id",
                "domain",
                "achievement",
                "date",
                "criterion",
                "level",
                "confidence",
                "source_url",
            ],
            where,
        )
        if r["id"] in seen:
            raise CuratedError(f"{where}: duplicate id")
        seen.add(r["id"])
        if not DATE_RE.match(r["date"]):
            raise CuratedError(f"{where}: bad date {r['date']!r}")
        if r["level"] not in SUPERHUMAN_LEVELS:
            raise CuratedError(f"{where}: level {r['level']!r} not in {sorted(SUPERHUMAN_LEVELS)}")
        if r["confidence"] not in CONFIDENCE:
            raise CuratedError(f"{where}: confidence {r['confidence']!r}")
    return sorted(rows, key=lambda r: r["date"])


def load_claims() -> list[dict]:
    rows = _read("claims.csv")
    seen: set[str] = set()
    for r in rows:
        where = f"claims.csv[{r.get('id')}]"
        _require(
            r, ["id", "set", "speaker", "date_said", "quote", "claim_summary", "source_url"], where
        )
        if r["id"] in seen:
            raise CuratedError(f"{where}: duplicate id")
        seen.add(r["id"])
        if r["set"] not in CLAIM_SETS:
            raise CuratedError(f"{where}: set {r['set']!r}")
        if not DATE_RE.match(r["date_said"]):
            raise CuratedError(f"{where}: bad date_said {r['date_said']!r}")
        r["horizon_lo"], r["horizon_hi"] = parse_horizon(r.get("horizon", ""), where)
    return rows


def load_manifold_markets() -> list[dict]:
    rows = _read("manifold_markets.csv")
    for r in rows:
        where = f"manifold_markets.csv[{r.get('id')}]"
        for f in ("id", "kind", "year"):
            if not (r.get(f) or "").strip():
                raise CuratedError(f"{where}: missing {f}")
        r["year"] = int(r["year"])
    return rows


def parse_horizon(text: str, where: str = "horizon") -> tuple[str | None, str | None]:
    """Turn a free-text horizon into an inclusive ISO date window (lo, hi).

    Accepted forms, all deterministic:
      ""            -> (None, None)               undated
      "2029"        -> 2029-01-01 .. 2029-12-31
      "2025-09"     -> 2025-09-01 .. 2025-09-30   (second part 01-12: a month)
      "2030-2035"   -> 2030-01-01 .. 2035-12-31   (second part four digits: a year range)
      "2020s"       -> 2020-01-01 .. 2029-12-31
      "2029; 2045"  -> the first horizon only; later ones belong in their own row
    Anything else raises, so a new phrasing is handled on purpose rather than guessed.
    """
    text = (text or "").strip()
    if not text:
        return None, None
    text = text.split(";")[0].strip()
    if m := re.fullmatch(r"(\d{4})s", text):
        y = int(m.group(1))
        return f"{y}-01-01", f"{y + 9}-12-31"
    if m := re.fullmatch(r"(\d{4})", text):
        return f"{text}-01-01", f"{text}-12-31"
    if m := re.fullmatch(r"(\d{4})\s*[-–]\s*(\d{4})", text):
        return f"{m.group(1)}-01-01", f"{m.group(2)}-12-31"
    if m := re.fullmatch(r"(\d{4})-(\d{2})", text):
        month = int(m.group(2))
        if 1 <= month <= 12:
            last = _month_end(int(m.group(1)), month)
            return f"{text}-01", f"{text}-{last:02d}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text, text
    raise CuratedError(f"{where}: unparseable horizon {text!r}")


def _month_end(year: int, month: int) -> int:
    if month == 12:
        return 31
    from datetime import date

    return date(year, month + 1, 1).toordinal() - date(year, month, 1).toordinal()
