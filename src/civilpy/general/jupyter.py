#  CivilPy
#  Copyright (C) 2019-2026 Dane Parks
#
#  SPDX-License-Identifier: MIT
#  See the LICENSE file in the project root for full license text.

"""Jupyter notebook export utilities.

Wraps ``nbconvert`` to render notebooks to PDF/WebPDF/HTML with cell-tag
filtering (``remove_cell``, ``remove_input``, ``remove_output``), so
calculation notebooks can be published as clean reports.
"""

import asyncio
import nbformat
from nbconvert import WebPDFExporter, PDFExporter, LatexExporter
from nbconvert.preprocessors import TagRemovePreprocessor


def notebook_converter(notebook_path, format='webpdf', text_width="70ch"):
    """Export a notebook, limiting rendered markdown to a readable line length.

    ``text_width`` caps the measure of markdown text in HTML-based exports
    (webpdf) so paragraphs read like an article instead of spanning the full
    page; code cells keep the full width. Pass ``None`` to disable. Ignored
    for the latex-based 'pdf' and 'latex' formats.
    """
    # Set the appropriate event loop policy for Windows
    if asyncio.get_event_loop().is_running():
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Read the notebook
    with open(notebook_path, 'r', encoding='utf-8') as f:
        notebook = nbformat.read(f, as_version=4)

    if format == 'webpdf' and text_width:
        style_cell = nbformat.v4.new_markdown_cell(
            "<style>\n"
            ".jp-RenderedMarkdown, .jp-MarkdownOutput "
            "{ max-width: " + text_width + "; }\n"
            "</style>"
        )
        notebook.cells.insert(0, style_cell)

    # Configure the tag removal preprocessor
    tag_remove_preprocessor = TagRemovePreprocessor()
    tag_remove_preprocessor.remove_cell_tags = ("remove_cell",)
    tag_remove_preprocessor.remove_single_output_tags = ("remove_output",)
    tag_remove_preprocessor.remove_input_tags = ("remove_input",)

    # Select the appropriate exporter based on the format
    if format == 'webpdf':
        exporter = WebPDFExporter()
        file_extension = ".pdf"
        write_mode = "wb"
    elif format == 'pdf':
        exporter = PDFExporter()
        file_extension = ".pdf"
        write_mode = "wb"
    elif format == 'latex':
        exporter = LatexExporter()
        file_extension = ".tex"
        write_mode = "w"
    else:
        raise ValueError("Unsupported format. Use 'webpdf', 'pdf', or 'latex'.")

    exporter.register_preprocessor(tag_remove_preprocessor, enabled=True)

    # Convert the notebook to the desired format
    data, resources = exporter.from_notebook_node(notebook)

    # Save the result to a file with the appropriate extension
    output_filename = notebook_path.replace(".ipynb", file_extension)
    with open(output_filename, write_mode, encoding="utf-8" if write_mode == "w" else None) as f:
        f.write(data)

    print(f"File created: {output_filename}")
