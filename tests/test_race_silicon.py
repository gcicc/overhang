"""Tests for the Race (holder spells, tenure), Compute & Silicon (data-center step
function, filed revenue and capex) — the rules a reader could not check by eye."""

from __future__ import annotations

from overhang import charts, compute, filings, race


def _p(date, value, org, model=None):
    return {"date": date, "value": value, "org": org, "model": model or f"{org}-{date}"}


# --- race -------------------------------------------------------------------


def test_spells_tie_keeps_earlier_holder_and_same_org_extends():
    pts = [
        _p("2024-01-01", 1.0, "OpenAI"),
        _p("2024-02-01", 1.0, "Anthropic"),  # ties: does not take the lead
        _p("2024-03-01", 2.0, "OpenAI"),  # holder's own record extends its spell
        _p("2024-04-01", 3.0, "Google DeepMind"),
        _p("2024-05-01", 0.5, "xAI"),  # below the record: ignored
    ]
    sp = race.spells(pts, "2024-06-01")
    assert [s["org"] for s in sp] == ["OpenAI", "Google"]
    assert sp[0]["records"] == 2 and sp[0]["end"] == "2024-04-01"
    assert sp[1]["ongoing"] and sp[1]["days"] == 61


def test_spells_clip_to_window_and_ignore_future_rows():
    pts = [_p("2022-01-01", 1.0, "OpenAI"), _p("2023-06-01", 2.0, "Anthropic")]
    pts.append(_p("2030-01-01", 9.0, "Google"))
    sp = race.spells(pts, "2024-01-01", start="2023-01-01")
    assert sp[0]["org"] == "OpenAI" and sp[0]["start"] == "2023-01-01" and sp[0]["clipped"]
    assert sp[-1]["org"] == "Anthropic" and sp[-1]["end"] == "2024-01-01"


def test_tenure_excludes_censored_spells():
    pts = [
        _p("2022-06-01", 1, "OpenAI"),
        _p("2023-03-01", 2, "Anthropic"),
        _p("2023-05-01", 3, "OpenAI"),
        _p("2023-09-01", 4, "Google"),
    ]
    t = race.tenure(race.spells(pts, "2024-01-01", start="2023-01-01"))
    # Clipped OpenAI spell at the start and the ongoing Google spell are both censored.
    assert t["completed_n"] == 2
    assert t["median_tenure_days"] == (61 + 123) / 2
    assert t["lead_changes"] == 3
    assert t["recent_median_days"] is None  # fewer than three completed spells


def test_country_share_dedupes_and_splits():
    pts = [
        {"date": "2024-01-01", "country": "United States of America,United States of America"},
        {"date": "2024-02-01", "country": "China,United Kingdom"},
        {"date": "2017-01-01", "country": "China"},  # before since_year
    ]
    s = race.country_share(pts, 2018)
    assert s["by_year"][2024] == {"US": 1.0, "China": 0.5, "Other": 0.5}
    assert s["n"] == 2


def test_normalise_org_merges_aliases():
    assert race.normalise_org("Google DeepMind,Google") == "Google"
    assert race.normalise_org("") == "Unknown"
    assert race.slot("Nvidia") == 1 and race.slot("Cambricon") == 0


# --- compute ----------------------------------------------------------------


def test_datacenter_projection_never_counts_as_current():
    dc = {
        "owners": {"A": {"owner": "Microsoft"}, "B": {"owner": "Microsoft"}},
        "timeline": [
            {"site": "A", "date": "2025-01-01", "h100e": 100.0},
            {"site": "A", "date": "2027-01-01", "h100e": 500.0},
            {"site": "B", "date": "2026-06-01", "h100e": 50.0},
        ],
    }
    out = compute.by_owner(dc, "2026-10-29")
    ms = out["owners"][0]
    assert ms["current"] == 150.0
    assert ms["planned"] == 550.0 and ms["planned_by"] == "2027-01-01"
    assert out["total"][-1] == {"date": "2026-10-29", "value": 150.0}


# --- filings ----------------------------------------------------------------


def _fact(start, end, val, form="10-Q", filed="2026-01-01"):
    return {"start": start, "end": end, "val": val, "form": form, "filed": filed}


def test_q4_derived_by_date_window_for_offset_fiscal_year():
    # Nvidia-style fiscal year ending late January.
    periods = {
        ("2025-01-27", "2025-04-27"): 10.0,
        ("2025-04-28", "2025-07-27"): 20.0,
        ("2025-07-28", "2025-10-26"): 30.0,
        ("2025-01-27", "2026-01-25"): 100.0,
    }
    q = filings.quarterly(periods)
    assert q[-1] == {"end": "2026-01-25", "value": 40.0, "derived": True}
    assert [p["derived"] for p in q[:3]] == [False, False, False]


def test_merge_prefers_current_concept_and_drops_10q_ttm():
    facts = {
        "us-gaap": {
            "Old": {"units": {"USD": [_fact("2020-01-01", "2020-03-31", 1.0)]}},
            "New": {
                "units": {
                    "USD": [
                        _fact("2020-01-01", "2020-03-31", 2.0),
                        _fact("2024-01-01", "2024-12-31", 9.0, form="10-K"),
                        # A trailing-twelve-month figure in a 10-Q is not a fiscal year.
                        _fact("2024-07-01", "2025-06-30", 11.0),
                    ]
                }
            },
        }
    }
    periods = filings.merge_facts(facts, ["Old", "New"])
    assert periods[("2020-01-01", "2020-03-31")] == 2.0
    assert ("2024-07-01", "2025-06-30") not in periods
    assert filings.annual(periods) == [{"end": "2024-12-31", "value": 9.0}]


def test_trailing_twelve_months():
    periods = {
        ("2024-01-01", "2024-12-31"): 100.0,
        ("2024-01-01", "2024-06-30"): 40.0,
        ("2025-01-01", "2025-12-31"): 120.0,
        ("2025-01-01", "2025-06-30"): 50.0,
        ("2026-01-01", "2026-06-30"): 80.0,
    }
    t = filings.trailing_twelve_months(periods)
    assert t == {"value": 150.0, "through": "2026-06-30", "basis": "TTM"}


# --- charts -----------------------------------------------------------------


def test_new_charts_are_deterministic_and_escaped():
    sp = race.spells([_p("2023-02-01", 1, "<b>Lab</b>")], "2024-01-01", start="2023-01-01")
    rows = [{"name": "Metric & co", "spells": sp}]
    a = charts.ribbon_chart(rows, 2023.0, 2024.0, race.slot, "r")
    assert a == charts.ribbon_chart(rows, 2023.0, 2024.0, race.slot, "r")
    assert "<b>" not in a and "&amp;" in a
    series = {"X <y>": {"slot": 1, "points": [(2020.0, 1.0), (2021.0, 10.0)]}}
    line = charts.lines_chart(series, 2021.5, fmt=str, log=True, label="l")
    assert "&lt;y&gt;" in line


# --- glossary ---------------------------------------------------------------


def test_glossary_wraps_text_only_and_prefers_longest_term():
    from overhang import render

    html = (
        "<head><title>AGI</title></head><p>ARC-AGI and AGI and TTM</p>"
        '<svg><text>FLOP</text></svg><a title="FLOP">x</a>'
    )
    out, used = render.gloss(html)
    assert "<title>AGI</title>" in out
    assert "<svg><text>FLOP</text></svg>" in out and 'title="FLOP"' in out
    assert used == ["ARC-AGI", "AGI", "TTM"]
    assert out.count('<abbr class="term"') == 3
