"""Render the payload into one self-contained HTML file (ADR 0001).

CSS and SVG are inlined. The page makes no requests of its own except Google Fonts,
and it falls back to system fonts, so it also opens from ``file://``.

After rendering, a glossary pass wraps every known acronym or term of art in the page
prose in ``<abbr title=...>`` (hover to read it), and the same definitions are listed in
a Glossary section, because touch screens cannot hover. Terms are matched in text only:
never inside tags, the ``<head>``, ``<style>`` or charts, whose SVG text cannot hold HTML.
"""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent / "templates"

# Term as it appears in the rendered HTML (so "&amp;" not "&") -> plain-English definition.
GLOSSARY = {
    "AGI": "Artificial general intelligence: roughly, AI that can do most cognitive work as "
    "well as a person. There is no single objective definition; see What counts as AGI?",
    "METR": "Model Evaluation & Threat Research, a nonprofit that measures how long a task "
    "AI agents can complete.",
    "time horizon": "The length of task (measured by how long it takes a skilled human) "
    "that a model completes successfully half the time.",
    "FLOP": "Floating-point operation, one arithmetic step on a computer. Training compute "
    "is the total number used to train a model.",
    "FLOP/s": "Floating-point operations per second: how fast a chip computes.",
    "PFLOP/s": "Peta-FLOP per second: 10^15 floating-point operations per second.",
    "H100e": "H100-equivalents: computing power expressed as the number of Nvidia H100 "
    "chips that would deliver the same throughput.",
    "GPQA Diamond": "Graduate-level Google-Proof Q&A: the hardest subset of multiple-choice "
    "science questions written by PhD experts so that they cannot be answered by searching.",
    "SWE-bench Verified": "Software-engineering benchmark: fix real issues from open-source "
    "Python projects. Verified is the subset human engineers confirmed are solvable.",
    "FrontierMath": "Epoch AI's benchmark of unpublished, research-level math problems. "
    "Tiers 1–3 are the less extreme levels; Tier 4 is the hardest.",
    "ARC-AGI": "Abstraction and Reasoning Corpus: grid puzzles that are easy for people and "
    "hard for AI, run by the ARC Prize Foundation.",
    "Epoch AI": "A research institute that tracks AI models, compute and benchmarks, and "
    "publishes its datasets openly.",
    "Manifold": "Manifold Markets, a prediction market where people bet play money on "
    "future events; prices read as probabilities.",
    "FP16/BF16": "16-bit number formats. Fewer bits per number means faster arithmetic and "
    "less precision; 16-bit is the format every AI chip generation reports.",
    "FP8": "8-bit number format: faster than 16-bit, less precise.",
    "FP4": "4-bit number format: faster still, least precise.",
    "TPU": "Tensor Processing Unit, Google's own AI chip.",
    "OLS": "Ordinary least squares: the standard straight-line fit.",
    "R²": "Share of the variation the fitted line explains (1 = a perfect fit).",
    "capex": "Capital expenditure: cash spent on long-lived assets such as buildings, "
    "servers and chips.",
    "TTM": "Trailing twelve months: the most recent four quarters added together.",
    "SEC": "U.S. Securities and Exchange Commission, which receives public companies' "
    "financial filings.",
    "EDGAR": "The SEC's public database of company filings.",
    "XBRL": "eXtensible Business Reporting Language: machine-readable tags on the numbers "
    "in a filing.",
    "10-K": "A U.S. company's audited annual report to the SEC.",
    "10-Q": "A U.S. company's quarterly report to the SEC.",
    "IFRS": "International Financial Reporting Standards, the accounting rules most "
    "non-U.S. companies use.",
    "TWD": "New Taiwan dollar.",
    "S&amp;P 500": "Index of 500 large U.S. companies' share prices, used as the market baseline.",
    "CC BY 4.0": "Creative Commons Attribution licence: free to reuse with credit.",
    "UTC": "Coordinated Universal Time (Greenwich time).",
    "1e15": "Scientific notation on chart axes: 1e15 means 10^15, a 1 followed by 15 zeros.",
}

# Longest first, so "SWE-bench Verified" wins over shorter overlaps and "ARC-AGI" over "AGI".
_TERMS = sorted(GLOSSARY, key=len, reverse=True)
_TERM_RE = re.compile(r"(?<![\w-])(" + "|".join(re.escape(t) for t in _TERMS) + r")(?![\w])")
# Regions the pass never touches, and single tags.
_SKIP_RE = re.compile(r"(<head>.*?</head>|<svg\b.*?</svg>|<style\b.*?</style>|<[^>]+>)", re.S)


def gloss(html: str) -> tuple[str, list[str]]:
    """Wrap glossary terms found in text; return the HTML and the terms used, in order."""
    used: list[str] = []

    def wrap(m: re.Match) -> str:
        term = m.group(1)
        if term not in used:
            used.append(term)
        return f'<abbr class="term" title="{escape(GLOSSARY[term])}">{term}</abbr>'

    parts = _SKIP_RE.split(html)
    out = [p if i % 2 else _TERM_RE.sub(wrap, p) for i, p in enumerate(parts)]
    return "".join(out), used


def glossary_section(terms: list[str]) -> str:
    rows = "".join(
        f"<dt>{t}</dt><dd>{escape(GLOSSARY[t])}</dd>"
        for t in sorted(terms, key=lambda t: t.lower().lstrip("1"))
    )
    return (
        '<section id="glossary"><h2>Glossary</h2>'
        '<p class="lede">Every dotted-underlined term on the page shows its definition on '
        "hover. The same definitions, for touch screens:</p>"
        f'<dl class="glossary">{rows}</dl></section>'
    )


def render(payload: dict, out: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["days"] = lambda d: "n/a" if d is None else f"{d:.0f} days"
    env.filters["pct"] = lambda v: "n/a" if v is None else f"{v:.0%}"
    html = env.get_template("page.html.j2").render(
        p=payload, styles=(TEMPLATES / "styles.css").read_text(encoding="utf-8")
    )
    html, used = gloss(html)
    html = html.replace("<!--GLOSSARY-->", glossary_section(used))
    out.write_text(html, encoding="utf-8")
    return out
