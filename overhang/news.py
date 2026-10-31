"""Recent AI news from RSS and Atom feeds, for the front page.

Standard library XML only (the dependency rule is ``requests`` and ``jinja2``). Selection
is deterministic: items are deduplicated on a normalised title, kept if published within
``MAX_AGE_DAYS``, and ordered newest first with a per-feed cap so one prolific feed
cannot fill a column. No ranking model, no LLM.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote

from overhang import net

ATOM = "{http://www.w3.org/2005/Atom}"


def _gnews(q: str) -> str:
    return (
        "https://news.google.com/rss/search?q="
        + quote(q + " when:7d")
        + "&hl=en-US&gl=US&ceid=US:en"
    )


# column -> feeds. Anthropic publishes no feed; the Google News query covers it.
FEEDS: dict[str, list[dict]] = {
    "labs": [
        {"name": "OpenAI", "url": "https://openai.com/news/rss.xml"},
        {"name": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
        {"name": "Hugging Face", "url": "https://huggingface.co/blog/feed.xml"},
        {
            "name": "Google News: labs",
            "url": _gnews(
                '(OpenAI OR Anthropic OR "Google DeepMind" OR Gemini OR "Meta AI" OR xAI) model'
            ),
        },
    ],
    "industry": [
        {
            "name": "Google News: chips & capital",
            "url": _gnews('(Nvidia OR "AI chips" OR "AI data center" OR hyperscaler capex) AI'),
        },
        {
            "name": "Google News: policy",
            "url": _gnews('("AI regulation" OR "AI Act" OR "AI policy" OR "AI safety institute")'),
        },
    ],
}
COLUMNS = {"labs": "From the labs", "industry": "Chips, capital & policy"}
PER_COLUMN = 12
PER_FEED = 5
MAX_AGE_DAYS = 7


def _date(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip()
    try:
        d = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def parse(xml_bytes: bytes, feed_name: str) -> list[dict]:
    """RSS 2.0 or Atom -> [{title, link, published, source}]."""
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter("item"):
        src = it.find("source")
        out.append(
            {
                "title": (it.findtext("title") or "").strip(),
                "link": (it.findtext("link") or "").strip(),
                "published": _date(it.findtext("pubDate")),
                "source": (src.text.strip() if src is not None and src.text else feed_name),
            }
        )
    for it in root.iter(ATOM + "entry"):
        link = it.find(ATOM + "link")
        out.append(
            {
                "title": (it.findtext(ATOM + "title") or "").strip(),
                "link": link.get("href", "") if link is not None else "",
                "published": _date(
                    it.findtext(ATOM + "published") or it.findtext(ATOM + "updated")
                ),
                "source": feed_name,
            }
        )
    return [e for e in out if e["title"] and e["link"]]


def _key(title: str) -> str:
    # Google News appends " - Outlet"; syndicated copies differ only there.
    t = re.sub(r"\s+-\s+[^-]{2,60}$", "", title)
    return re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()


def select(entries: list[dict], now: datetime, seen: set[str]) -> list[dict]:
    """Dedupe (across columns via ``seen``), drop old or undated, newest first, capped."""
    cutoff = now - timedelta(days=MAX_AGE_DAYS)
    fresh = sorted(
        (
            e
            for e in entries
            if e["published"] and cutoff <= e["published"] <= now + timedelta(hours=1)
        ),
        key=lambda e: e["published"],
        reverse=True,
    )
    per_feed: dict[str, int] = {}
    chosen = []
    for e in fresh:
        k = _key(e["title"])
        if k in seen or per_feed.get(e["feed"], 0) >= PER_FEED:
            continue
        seen.add(k)
        per_feed[e["feed"]] = per_feed.get(e["feed"], 0) + 1
        chosen.append(e)
        if len(chosen) == PER_COLUMN:
            break
    return chosen


def fetch() -> dict:
    """Fetch every feed. One feed failing is logged and skipped; all failing raises."""
    now = datetime.now(UTC)
    seen: set[str] = set()
    columns, errors, ok = {}, [], 0
    for col, feeds in FEEDS.items():
        entries = []
        for f in feeds:
            try:
                got = parse(net.get(f["url"]).content, f["name"])
                ok += 1
            except Exception as exc:  # noqa: BLE001 - one bad feed must not sink the rest
                errors.append(f"{f['name']}: {type(exc).__name__}")
                continue
            for e in got:
                e["feed"] = f["name"]
            entries.extend(got)
        columns[col] = [
            {**e, "published": e["published"].isoformat(timespec="minutes")}
            for e in select(entries, now, seen)
        ]
    if not ok:
        raise RuntimeError("every news feed failed: " + "; ".join(errors))
    # Column order is explicit: the JSON cache does not preserve key order.
    return {"columns": columns, "labels": COLUMNS, "order": list(COLUMNS), "errors": errors}
