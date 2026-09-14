"""Checkpoint ownership for production and isolated tests."""

from contextlib import contextmanager
from typing import Iterator

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver

from ..core.config import get_settings


def postgres_connection_string(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def workflow_checkpointer() -> Iterator[BaseCheckpointSaver]:
    settings = get_settings()
    if settings.langgraph_checkpoint_mode == "memory":
        yield InMemorySaver()
        return
    with PostgresSaver.from_conn_string(postgres_connection_string(settings.database_url)) as saver:
        saver.setup()
        yield saver
