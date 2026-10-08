"""Render the payload into one self-contained HTML file (ADR 0001).

CSS and SVG are inlined. The page makes no requests of its own except Google Fonts,
and it falls back to system fonts, so it also opens from ``file://``.
"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES = Path(__file__).resolve().parent / "templates"


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
    out.write_text(html, encoding="utf-8")
    return out
