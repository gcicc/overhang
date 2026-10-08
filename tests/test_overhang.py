"""Tests for the rules the spec makes testable: sourcing (D2/D3), status (D5),
fits (D4), determinism (D6) and honest degradation (D8)."""

from __future__ import annotations

import math
from datetime import date

import pytest

from overhang import charts, curated, quotecheck, resolve, sources, trend

# --- METR YAML subset parser -----------------------------------------------

METR_SAMPLE = """\
benchmark_name: METR-Horizon-v1.1
doubling_time_in_days: # excludes points with central estimate p50 > 16 hrs
  from_2023_on:
    ci_high: 158.012
    point_estimate: 128.744
results:
  model_a:
    metrics:
      is_sota: true
      p50_horizon_length:
        ci_high: 22.3
        ci_low: 5.4
        estimate: 11.39
    release_date: 2024-06-20
    scaffolds:
    - mtb/start_metr_task,metr_agents/react
  model_b:
    metrics:
      p50_horizon_length:
        estimate: 20.5
    release_date: 2024-10-22
"""


def test_parse_simple_yaml_nesting_and_comments():
    doc = sources.parse_simple_yaml(METR_SAMPLE)
    assert doc["doubling_time_in_days"]["from_2023_on"]["point_estimate"] == "128.744"
    a = doc["results"]["model_a"]
    assert a["release_date"] == "2024-06-20"
    assert a["metrics"]["p50_horizon_length"]["estimate"] == "11.39"
    assert a["metrics"]["is_sota"] == "true"
    assert "scaffolds" in a and a["scaffolds"] == {}  # list items are skipped
    assert doc["results"]["model_b"]["metrics"]["p50_horizon_length"]["estimate"] == "20.5"


# --- trend ------------------------------------------------------------------


def _series(doubling_days: float, n: int = 8, start: float = 2023.0) -> list[dict]:
    """Exact exponential series with a known doubling time."""
    pts = []
    for i in range(n):
        t = start + i * 0.25
        pts.append(
            {
                "date": trend.from_year(t),
                "value": 2 ** ((t - start) * 365.25 / doubling_days),
                "model": f"m{i}",
            }
        )
    return pts


def test_fit_recovers_known_doubling_time():
    fit = trend.fit_doubling(_series(120.0), "2020-01-01")
    assert fit["doubling_days"] == pytest.approx(120.0, rel=0.01)
    assert fit["r2"] == pytest.approx(1.0, abs=1e-4)  # dates are rounded to whole days
    assert fit["n"] == 8


def test_fit_reports_its_window_and_needs_three_points():
    pts = _series(200.0)
    fit = trend.fit_doubling(pts, "2023-06-01")
    assert fit["window_start"] >= "2023-06-01"
    assert fit["window_end"] == pts[-1]["date"]
    assert trend.fit_doubling(pts[:2], "2000-01-01") is None


def test_frontier_is_running_maximum():
    pts = [
        {"date": "2024-01-01", "value": 1.0},
        {"date": "2024-02-01", "value": 0.5},
        {"date": "2024-03-01", "value": 2.0},
        {"date": "2024-04-01", "value": 2.0},
    ]
    assert [p["date"] for p in trend.frontier(pts)] == ["2024-01-01", "2024-03-01"]


def test_crossing_date_matches_fit():
    fit = trend.fit_doubling(_series(365.25), "2020-01-01")  # doubles once a year from 1
    assert trend.crossing_date(fit, 8.0)[:7] == "2026-01"


def test_year_round_trip():
    for d in ("2024-02-29", "2025-12-31", "1997-05-11"):
        assert trend.from_year(trend.to_year(d)) == d


# --- horizons and status (D5) ----------------------------------------------


@pytest.mark.parametrize(
    "text, expected",
    [
        ("", (None, None)),
        ("2029", ("2029-01-01", "2029-12-31")),
        ("2025-09", ("2025-09-01", "2025-09-30")),
        ("2030-2035", ("2030-01-01", "2035-12-31")),
        ("2020s", ("2020-01-01", "2029-12-31")),
        ("2029; 2045", ("2029-01-01", "2029-12-31")),
        ("2024-02", ("2024-02-01", "2024-02-29")),
    ],
)
def test_parse_horizon(text, expected):
    assert curated.parse_horizon(text) == expected


def test_parse_horizon_rejects_unknown_phrasing():
    with pytest.raises(curated.CuratedError):
        curated.parse_horizon("soon-ish")


def _claim(lo, hi):
    return {"id": "x", "horizon_lo": lo, "horizon_hi": hi}


def test_status_never_says_missed():
    today = date(2026, 10, 8)
    assert resolve.claim_status(_claim(None, None), today, None, {})["status"] == "undated"
    assert (
        resolve.claim_status(_claim("2028-01-01", "2028-12-31"), today, None, {})["status"]
        == "open"
    )
    assert (
        resolve.claim_status(_claim("2026-01-01", "2027-12-31"), today, None, {})["status"]
        == "window_open"
    )
    passed = resolve.claim_status(_claim("2000-01-01", "2000-12-31"), today, None, {})
    assert passed["status"] == "passed_unverified"
    assert "unverified" in passed["label"]
    assert "missed" not in " ".join(resolve.STATUS_LABEL.values())


def test_status_achieved_reports_lag():
    events = {"chess": {"id": "chess", "date": "1997-05-11", "achievement": "Deep Blue"}}
    res = {"superhuman_id": "chess", "rationale": "match win"}
    s = resolve.claim_status(_claim("1968-01-01", "1968-12-31"), date(2026, 1, 1), res, events)
    assert s["status"] == "achieved"
    assert s["lag_years"] == pytest.approx(28.4, abs=0.1)


# --- curated validation (D2) -----------------------------------------------


def test_curated_rejects_row_without_source(tmp_path, monkeypatch):
    (tmp_path / "superhuman.csv").write_text(
        "id,domain,achievement,date,criterion,level,confidence,source_url\n"
        "a,games,won,1997-05-11,match,exceeded_best,high,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(curated, "CURATED", tmp_path)
    with pytest.raises(curated.CuratedError, match="source_url"):
        curated.load_superhuman()


def test_curated_rejects_bad_level(tmp_path, monkeypatch):
    (tmp_path / "superhuman.csv").write_text(
        "id,domain,achievement,date,criterion,level,confidence,source_url\n"
        "a,games,won,1997-05-11,match,superhuman,high,https://example.org\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(curated, "CURATED", tmp_path)
    with pytest.raises(curated.CuratedError, match="level"):
        curated.load_superhuman()


def test_shipped_curated_data_is_valid():
    claims = curated.load_claims()
    events = curated.load_superhuman()
    resolve.load_resolutions({e["id"] for e in events}, {c["id"] for c in claims})
    assert all(c["source_url"].startswith("http") for c in claims)
    assert len({c["id"] for c in claims}) == len(claims)


# --- quote check (D3) ------------------------------------------------------


def test_quote_match_handles_typography_and_ellipsis():
    page = quotecheck.normalise("<p>He said: “It’s a long road, and we will get there soon.”</p>")
    assert quotecheck.match("It's a long road, and we will get there soon.", page) == "verbatim"
    assert quotecheck.match("It's a long road ... we will get there soon", page) == "verbatim"
    assert quotecheck.match("Something nobody wrote down anywhere at all", page) == "not_found"


def test_quote_match_survives_pdf_hyphenation():
    page = quotecheck.normalise(
        "the chance that high-\nlevel machine intelligence will be developed"
    )
    assert (
        quotecheck.match("chance that high-level machine intelligence will be developed", page)
        == "verbatim"
    )


# --- charts (D6) -----------------------------------------------------------


def test_charts_are_deterministic_and_escaped():
    pts = _series(150.0)
    pts[0]["model"] = "<script>x</script>"
    front = trend.frontier(pts)
    fit = trend.fit_doubling(front, "2020-01-01")
    a = charts.trend_chart(pts, front, fit, 2025.5)
    b = charts.trend_chart(pts, front, fit, 2025.5)
    assert a == b
    assert "<script>" not in a and "&lt;script&gt;" in a


def test_fmt_minutes():
    assert charts.fmt_minutes(30) == "30 min"
    assert charts.fmt_minutes(120) == "2 h"
    assert math.isclose(len(charts.fmt_flop(1e27)), 4)
