"""Tests for the History timeline: sector collapse, ledger validation, and the chart rules
a reader could not check by eye (winters shaded, milestones never take a sector colour)."""

from __future__ import annotations

import pytest

from overhang import charts, curated, sources


def test_sector_collapses_multi_org_categories():
    assert sources.sector("Academia") == "academia"
    assert sources.sector("Industry,Industry") == "industry"
    assert sources.sector("Academia,Industry,Academia") == "both"
    assert sources.sector("Research collective") == "other"
    assert sources.sector("") == "other"


def test_history_ledger_loads_and_winters_have_end_dates():
    rows = curated.load_history()
    assert rows == sorted(rows, key=lambda r: r["date"])
    winters = [r for r in rows if r["lane"] == "winter"]
    assert winters and all(r["date_end"] for r in winters)
    assert all(r["quote_verified"] == "yes" for r in rows)


def _write(tmp_path, row: str) -> None:
    (tmp_path / "history.csv").write_text(
        "id,date,date_end,date_precision,lane,kind,title,who,quote,quote_verified,source_url\n"
        + row
        + "\n",
        encoding="utf-8",
    )


def test_history_rejects_winter_without_end_and_unknown_lane(tmp_path, monkeypatch):
    monkeypatch.setattr(curated, "CURATED", tmp_path)
    _write(tmp_path, "w,1974,,year,winter,winter,Winter,,a quote,yes,https://example.org")
    with pytest.raises(curated.CuratedError, match="date_end"):
        curated.load_history()
    _write(tmp_path, "x,1990,,year,military,event,Thing,,a quote,yes,https://example.org")
    with pytest.raises(curated.CuratedError, match="lane"):
        curated.load_history()


def test_history_chart_shades_winters_and_keeps_milestones_neutral():
    notable = [
        {"model": "<Net>", "org": "Lab", "date": "1990-01-01", "value": 1e10, "sector": "academia"},
        {"model": "Big", "org": "Co", "date": "2024-01-01", "value": 1e25, "sector": "industry"},
    ]
    history = [
        {
            "id": "w1",
            "lane": "winter",
            "date": "1974",
            "date_end": "1980",
            "title": "First AI winter",
        },
        {"id": "h1", "lane": "industry", "date": "2022-11-30", "title": "ChatGPT", "who": "OpenAI"},
    ]
    sh = [
        {
            "id": "s1",
            "date": "1997-05-11",
            "achievement": "Chess",
            "level": "exceeded_best",
            "confidence": "high",
        }
    ]
    svg = charts.history_timeline(notable, history, sh, 2026.8, "History")
    assert svg.count('class="winter"') == 1
    assert "&lt;Net&gt;" in svg and "<Net>" not in svg
    assert 'class="cat c7"' in svg and 'class="cat c4"' in svg
    assert 'href="#h1"><circle class="ms"' in svg
    assert 'href="#s1"><circle class="ms-first"' in svg
    assert "lv-exceeded" not in svg
