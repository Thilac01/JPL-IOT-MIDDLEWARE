"""Backward-compatibility shim for config module."""
from app.core.config import settings, Settings

__all__ = ["settings", "Settings"]
