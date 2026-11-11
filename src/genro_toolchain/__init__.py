"""Standalone build tools for Genropy applications."""

__version__ = "0.1.0"


class ToolchainError(Exception):
    """A user-facing error: printed without a traceback, exits with status 1."""
