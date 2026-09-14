"""Thin ASGI compatibility entrypoint for ``uvicorn app.main:app``."""

from .api.application import app

__all__ = ["app"]
