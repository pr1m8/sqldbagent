"""Sphinx configuration for the public sqldbagent documentation."""

from __future__ import annotations

import sys
from importlib.metadata import version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

project = "sqldbagent"
author = "Will"
release = package_version("sqldbagent")
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx_togglebutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.mermaid",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_class_signature = "mixed"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_use_ivar = True
napoleon_attr_annotations = False

html_theme = "furo"
html_title = "sqldbagent"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_theme_options = {
    "source_repository": "https://github.com/pr1m8/sqldbagent/",
    "source_branch": "main",
    "source_directory": "docs/source/",
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "linkify",
]

mermaid_output_format = "raw"
