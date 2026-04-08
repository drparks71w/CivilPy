# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys

# Add the src directory so autodoc can import civilpy modules
sys.path.insert(0, os.path.abspath("../src"))

# -- Project information -----------------------------------------------------
project = "CivilPy"
copyright = "2019-2026, Dane Parks"
author = "Dane Parks"
release = "0.1.38"

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.coverage",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

# Napoleon settings for Google/NumPy-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True

# Intersphinx: link to Python and NumPy docs
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
}

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autodoc_mock_imports = [
    "rhinoinside",
    "Rhino",
    "winreg",
    "psycopg",
    "oracledb",
    "torch",
    "torchvision",
    "camelot",
    "FreeSimpleGUI",
    "pytesseract",
    "selenium",
    "folium",
    "tifftools",
    "nbformat",
    "nbconvert",
    "plotly",
    "pydantic",
    "sshtunnel",
    "fitz",
    "google",
    "google.generativeai",
    "natsort",
]

autosummary_generate = True
todo_include_todos = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
}
html_static_path = ["_static"]
