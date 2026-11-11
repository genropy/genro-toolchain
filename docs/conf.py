"""Sphinx configuration for the genro-toolchain documentation."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

project = "genro-toolchain"
author = "Genropy Team"
copyright = "Genropy Team"

# Read the version from the package without importing it.
_init = (ROOT / "src" / "genro_toolchain" / "__init__.py").read_text(encoding="utf-8")
release = re.search(r'__version__ = "([^"]+)"', _init).group(1)
version = ".".join(release.split(".")[:2])

extensions = [
    "myst_parser",
    "sphinx_copybutton",
]

source_suffix = {".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]
myst_heading_anchors = 3

html_theme = "sphinx_rtd_theme"
html_title = f"{project} {release}"
html_context = {
    "display_github": True,
    "github_user": "genropy",
    "github_repo": "genro-toolchain",
    "github_version": "main",
    "conf_py_path": "/docs/",
}
