"""Front page: upcoming-milestone ledger, news selection, cross-page anchors."""

from datetime import UTC, datetime, timedelta

import pytest

from overhang import curated, news, render


def test_upcoming_ledger_validates_and_is_sorted():
    rows = curated.load_upcoming()
    assert rows
    keys = [(r["date"], r.get("time_utc") or "") for r in rows]
    assert keys == sorted(keys)
    for r in rows:
        assert (r["precision"] == "minute") == bool(r.get("time_utc"))


def test_upcoming_rejects_time_on_day_precision(monkeypatch):
    row = {
        "id": "x",
        "date": "2027-01-01",
        "time_utc": "10:00",
        "precision": "day",
        "kind": "conference",
        "title": "t",
        "who": "w",
        "quote": "q",
        "source_url": "https://example.com",
    }
    monkeypatch.setattr(curated, "_read", lambda name: [row])
    with pytest.raises(curated.CuratedError, match="minute precision"):
        curated.load_upcoming()


def test_news_select_dedupes_syndicated_copies_and_drops_old():
    now = datetime(2026, 10, 31, tzinfo=UTC)

    def e(title, hours, feed="f"):
        return {
            "title": title,
            "link": "https://x/" + title,
            "feed": feed,
            "published": now - timedelta(hours=hours),
            "source": "s",
        }

    items = [
        e("Big model ships - Reuters", 1),
        e("Big model ships - CNBC", 2),
        e("Old story", 24 * 9),
        e("Newer story", 0.5),
    ]
    got = news.select(items, now, set())
    assert [g["title"] for g in got] == ["Newer story", "Big model ships - Reuters"]


def test_news_parse_rss_and_atom():
    rss = b"""<rss><channel><item><title>A</title><link>https://a</link>
      <pubDate>Fri, 30 Oct 2026 09:30:00 GMT</pubDate><source url="x">Outlet</source></item>
      </channel></rss>"""
    atom = b"""<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>B</title>
      <link href="https://b"/><updated>2026-10-30T10:00:00Z</updated></entry></feed>"""
    a = news.parse(rss, "F")[0]
    b = news.parse(atom, "G")[0]
    assert (a["source"], a["published"].hour) == ("Outlet", 9)
    assert (b["link"], b["source"]) == ("https://b", "G")


def test_cross_links_point_to_the_other_page():
    html = '<section id="measured"></section><a href="#measured">m</a><a href="#cu24">c</a>'
    out = render._cross_links(html, "main")
    assert 'href="#measured"' in out
    assert 'href="claims.html#cu24"' in out
