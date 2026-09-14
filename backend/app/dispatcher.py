"""Thin Dispatcher compatibility entrypoint for ``python -m app.dispatcher``."""

from .workers.dispatcher import run

if __name__ == "__main__":
    run()
