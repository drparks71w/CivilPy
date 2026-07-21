#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""ODOT visual branding for the CivilPy notebook series.

Provides the ODOT brand palette, a sanitizer-safe HTML title block for
notebook headers, the stylesheet injected into branded PDF exports, and
``stamp_title_block`` to add/refresh the header cell in a ``.ipynb`` file.

Hex values are the published ODOT brand colors (transportation.ohio.gov/brand).
The neutral gray is not from the brand guide; barrel orange is part of the
palette but its hex isn't published outside the brand toolkit, so it is
omitted here. The official logo is trademarked and not distributed with
CivilPy — drop a licensed copy at ``Notebooks/res/odot_logo.png`` and the
title block will embed it automatically.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from pathlib import Path

ODOT_COLORS = {
    "primary_blue": "#0E3F75",
    "cardinal_red": "#C12637",
    "zephyr_green": "#00855B",
    "neutral_gray": "#54585A",
}

TITLE_BLOCK_MARKER = "<!-- civilpy-title-block -->"

DEFAULT_LOGO_PATH = Path(__file__).parents[5] / "Notebooks" / "res" / "odot_logo.png"


def logo_data_uri(path=None):
    """Return the logo as a ``data:`` URI, or None if the file doesn't exist."""
    path = Path(path) if path else DEFAULT_LOGO_PATH
    if not path.is_file():
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def title_block_html(title, organization="Ohio Department of Transportation",
                     series="CivilPy Notebook Series", logo_path=None):
    """Sanitizer-safe (inline styles only) header div for a notebook.

    Renders in JupyterLab markdown cells, which strip ``<style>`` tags but
    allow styled ``<div>``/``<span>``/``<img>`` elements.
    """
    c = ODOT_COLORS
    logo = logo_data_uri(logo_path)
    logo_img = (
        f'<img src="{logo}" alt="ODOT logo" '
        'style="height:3em; float:right; margin-left:1em;">' if logo else ""
    )
    return (
        f"{TITLE_BLOCK_MARKER}\n"
        f'<div style="border-top:6px solid {c["primary_blue"]}; '
        f'border-bottom:2px solid {c["cardinal_red"]}; '
        'padding:0.6em 0 0.6em 0; margin-bottom:1.2em;">\n'
        f"{logo_img}"
        f'<span style="font-size:1.5em; font-weight:bold; '
        f'color:{c["primary_blue"]};">{title}</span><br>\n'
        f'<span style="color:{c["neutral_gray"]};">{organization} '
        f"&middot; {series}</span>\n"
        "</div>"
    )


def export_css(text_width="70ch"):
    """Stylesheet injected into HTML-based (webpdf) exports.

    Brand colors on headings plus the readable-measure cap on markdown text;
    ``text_width=None`` drops the cap.
    """
    c = ODOT_COLORS
    measure = (
        ".jp-RenderedMarkdown, .jp-MarkdownOutput "
        f"{{ max-width: {text_width}; }}\n" if text_width else ""
    )
    return (
        "<style>\n"
        f"{measure}"
        ".jp-RenderedMarkdown h1, .jp-RenderedMarkdown h2 "
        f"{{ color: {c['primary_blue']}; }}\n"
        ".jp-RenderedMarkdown h1 "
        f"{{ border-bottom: 2px solid {c['cardinal_red']}; "
        "padding-bottom: 0.2em; }\n"
        ".jp-RenderedMarkdown h3 "
        f"{{ color: {c['neutral_gray']}; }}\n"
        "</style>"
    )


def notebook_title(notebook_path):
    """Display title derived from the notebook filename."""
    return Path(notebook_path).stem.replace("_", " ")


def stamp_title_block(notebook_path, title=None, logo_path=None):
    """Insert (or refresh) the branded title-block cell at the top of a notebook.

    Idempotent: an existing cell containing ``TITLE_BLOCK_MARKER`` is replaced
    in place. Edits the raw JSON to preserve the file's existing formatting.

    Note this brands the notebook file itself — only appropriate for actual
    ODOT deliverables. For everything else, leave the notebook unbranded and
    pass ``branding='odot'`` to ``notebook_converter`` so the title block
    exists only in the generated PDF.
    """
    notebook_path = Path(notebook_path)
    raw = notebook_path.read_text(encoding="utf-8")
    had_newline = raw.endswith("\n")
    nb = json.loads(raw)

    html = title_block_html(title or notebook_title(notebook_path),
                            logo_path=logo_path)
    source = [line + "\n" for line in html.split("\n")]
    source[-1] = source[-1].rstrip("\n")

    cell = {"cell_type": "markdown", "metadata": {}, "source": source}
    if nb.get("nbformat_minor", 0) >= 5:
        cell = {"cell_type": "markdown", "id": str(uuid.uuid4())[:8],
                "metadata": {}, "source": source}

    for existing in nb["cells"]:
        src = existing.get("source", "")
        text = src if isinstance(src, str) else "".join(src)
        if existing.get("cell_type") == "markdown" and TITLE_BLOCK_MARKER in text:
            existing["source"] = source
            break
    else:
        nb["cells"].insert(0, cell)

    out = json.dumps(nb, indent=1, ensure_ascii=False)
    if had_newline:
        out += "\n"
    notebook_path.write_text(out, encoding="utf-8")


def remove_title_block(notebook_path):
    """Remove any stamped title-block cell, preserving file formatting."""
    notebook_path = Path(notebook_path)
    raw = notebook_path.read_text(encoding="utf-8")
    had_newline = raw.endswith("\n")
    nb = json.loads(raw)

    kept = []
    for cell in nb["cells"]:
        src = cell.get("source", "")
        text = src if isinstance(src, str) else "".join(src)
        if cell.get("cell_type") == "markdown" and TITLE_BLOCK_MARKER in text:
            continue
        kept.append(cell)
    if len(kept) == len(nb["cells"]):
        return False
    nb["cells"] = kept

    out = json.dumps(nb, indent=1, ensure_ascii=False)
    if had_newline:
        out += "\n"
    notebook_path.write_text(out, encoding="utf-8")
    return True
