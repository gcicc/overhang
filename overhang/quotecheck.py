"""Check that every curated quote still appears verbatim at its source.

Runs weekly as an ordinary cached source. Each quote is normalised (case, punctuation,
typographic quotes, whitespace, tags) and searched for in the normalised text of its
source page. A quote containing an ellipsis passes only if every fragment is found.

Results feed the page as a per-row badge. A ``not_found`` is shown, never hidden: the
page may have moved, or the quote may be wrong, and the reader should know which rows
cannot currently be confirmed.

PDFs are read with ``pdftotext`` (poppler-utils) when it is installed; without it they
are reported as ``pdf_unchecked`` rather than guessed at.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

from overhang import net


def normalise(text: str) -> str:
    text = html.unescape(text)
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'), ("”", '"'), ("ﬁ", "fi"), ("ﬂ", "fl")):
        text = text.replace(a, b)
    text = re.sub(r"<[^>]+>", " ", text)
    # Rejoin words hyphenated across a line break, as PDF extraction produces them.
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def fragments(quote: str) -> list[str]:
    parts = re.split(r"\.\.\.|…|\[\.\.\.\]", quote)
    frags = [normalise(p) for p in parts]
    return [f for f in frags if len(f) > 15] or [normalise(quote)]


def match(quote: str, page_text: str) -> str:
    # Spaces are compared out as well: line-end hyphenation makes "high-level" read as
    # "highlevel" in a PDF, and only whitespace or punctuation can differ at that point.
    squashed = page_text.replace(" ", "")
    frags = fragments(quote)
    hits = sum(f in page_text or f.replace(" ", "") in squashed for f in frags)
    if hits == len(frags):
        return "verbatim"
    return "partial" if hits else "not_found"


def _page_text(url: str) -> str | None:
    resp = net.get(url, retries=1)
    is_pdf = url.lower().endswith(".pdf") or "pdf" in resp.headers.get("Content-Type", "")
    if not is_pdf:
        return normalise(resp.text)
    if not shutil.which("pdftotext"):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "src.pdf"
        pdf.write_bytes(resp.content)
        out = subprocess.run(
            ["pdftotext", str(pdf), "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        ).stdout
    # PDF hyphenation must be rejoined before newlines are flattened.
    return normalise(re.sub(r"(\w)-\n(\w)", r"\1\2", out))


def fetch(claims: list[dict]) -> dict:
    pages: dict[str, str | None | Exception] = {}
    results = {}
    for c in claims:
        url = c["source_url"]
        if url not in pages:
            try:
                pages[url] = _page_text(url)
            except Exception as e:  # noqa: BLE001 - a dead source is a result, not a crash
                pages[url] = e
            time.sleep(1)
        page = pages[url]
        if isinstance(page, Exception):
            status, detail = "fetch_failed", f"{type(page).__name__}"
        elif page is None:
            status, detail = "pdf_unchecked", "pdftotext not installed"
        else:
            status, detail = match(c["quote"], page), ""
        results[c["id"]] = {"status": status, "detail": detail}
    return {"results": results, "checked_at": datetime.now(UTC).isoformat(timespec="seconds")}
