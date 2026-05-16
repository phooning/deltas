"""Compatibility shim for the historical hyphenated app path.

The runnable Python package is trading_desk because hyphenated directories are
not importable as Python packages. This file keeps the old path discoverable.
"""

from trading_desk.app import AppState, create_app

__all__ = ["AppState", "create_app"]
