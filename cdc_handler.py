"""Backward-compatibility shim for cdc_handler module."""
from app.services.cdc_engine import CDCEngine as CDCHandler

__all__ = ["CDCHandler"]
