"""Manic AI API entry point.

Run with:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8081
"""
from api.app import app  # noqa: F401
