"""Sphinx configuration for the public sqldbagent documentation."""

from __future__ import annotations

import os
import sys
from datetime import date
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


def _package_release() -> str:
    """Return the installed sqldbagent version when available."""

    try:
        return package_version("sqldbagent")
    except PackageNotFoundError:
        return "0.0.0"


def _build_intersphinx_mapping() -> dict[str, tuple[str, str | None]]:
    """Return intersphinx targets for environments that can resolve them."""

    if (
        os.environ.get("READTHEDOCS") != "True"
        and os.environ.get(
            "SPHINX_ENABLE_INTERSPHINX",
            "0",
        )
        != "1"
    ):
        return {}

    return {
        "python": ("https://docs.python.org/3", None),
        "pydantic": ("https://docs.pydantic.dev/latest/", None),
        "sqlalchemy": ("https://docs.sqlalchemy.org/en/20/", None),
    }


project = "sqldbagent"
author = "Will"
copyright = f"{date.today().year}, Will"
release = _package_release()
version = release
language = "en"
default_role = "literal"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.autosummary",
    "sphinx.ext.duration",
    "sphinx.ext.extlinks",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
    "sphinx_last_updated_by_git",
    "sphinx_togglebutton",
    "sphinx_inline_tabs",
    "sphinxcontrib.autodoc_pydantic",
    "sphinxcontrib.mermaid",
    "sphinxext.opengraph",
    "notfound.extension",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
suppress_warnings = ["sphinx_autodoc_typehints.guarded_import"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

autosummary_generate = True
autosummary_imported_members = False
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_typehints_format = "short"
autodoc_class_signature = "mixed"
autodoc_preserve_defaults = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_use_ivar = True
napoleon_attr_annotations = False
always_document_param_types = True
always_use_bars_union = True
typehints_defaults = "comma"
python_use_unqualified_type_names = True

autosectionlabel_prefix_document = True
todo_include_todos = False
todo_emit_warnings = True

extlinks = {
    "issue": ("https://github.com/pr1m8/sqldbagent/issues/%s", "#%s"),
    "pr": ("https://github.com/pr1m8/sqldbagent/pull/%s", "PR #%s"),
    "src": ("https://github.com/pr1m8/sqldbagent/blob/main/%s", "%s"),
}

intersphinx_mapping = _build_intersphinx_mapping()
intersphinx_timeout = 5

html_theme = "furo"
html_title = "sqldbagent"
html_baseurl = os.environ.get(
    "READTHEDOCS_CANONICAL_URL",
    "https://sqldbagent.readthedocs.io/en/latest/",
)
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_last_updated_fmt = "%b %d, %Y"
html_theme_options = {
    "source_repository": "https://github.com/pr1m8/sqldbagent/",
    "source_branch": "main",
    "source_directory": "docs/source/",
    "navigation_with_keys": True,
    "top_of_page_button": "edit",
}

myst_enable_extensions = [
    "attrs_block",
    "attrs_inline",
    "colon_fence",
    "deflist",
    "linkify",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_url_schemes = ("http", "https", "mailto")

copybutton_prompt_text = r">>> |\.\.\. |\$ "
copybutton_prompt_is_regexp = True

ogp_site_url = html_baseurl
ogp_site_name = project
ogp_enable_meta_description = True
ogp_description_length = 240

if html_baseurl.startswith("https://sqldbagent.readthedocs.io/"):
    notfound_urls_prefix = "/en/latest/"

mermaid_output_format = "raw"
