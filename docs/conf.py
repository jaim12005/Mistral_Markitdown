"""Sphinx configuration for Enhanced Document Converter."""

project = "Enhanced Document Converter"
copyright = "2025, Enhanced Document Converter Contributors"
author = "Enhanced Document Converter Contributors"
release = "3.0.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

autodoc_member_order = "bysource"
napoleon_google_docstring = True
napoleon_numpy_docstring = False
