"""Add quasi-production task, audit, and model invocation foundation."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

from app.infrastructure.database import Base
from app.domain import models  # noqa: F401


revision = "20260914_0001"
down_revision = None
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _add(table: str, column: sa.Column):
    if column.name not in _columns(table):
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    _add("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"))

    _add("content_documents", sa.Column("task_id", sa.Integer(), nullable=True))
    _add("generation_tasks", sa.Column("retry_of_task_id", sa.Integer(), nullable=True))
    _add("generation_tasks", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    _add("generation_tasks", sa.Column("request_id", sa.String(length=64), nullable=True))
    _add("generation_tasks", sa.Column("input_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    _add("generation_tasks", sa.Column("version", sa.Integer(), nullable=False, server_default="1"))

    _add("experiments", sa.Column("created_by_id", sa.Integer(), nullable=True))
    _add("experiments", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    _add("experiments", sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    _add("experiments", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))

    inspector = inspect(bind)
    foreign_keys = {fk.get("name") for fk in inspector.get_foreign_keys("content_documents")}
    if "fk_content_documents_task_id" not in foreign_keys:
        op.create_foreign_key("fk_content_documents_task_id", "content_documents", "generation_tasks", ["task_id"], ["id"], ondelete="SET NULL")
    foreign_keys = {fk.get("name") for fk in inspect(bind).get_foreign_keys("generation_tasks")}
    if "fk_generation_tasks_retry_of" not in foreign_keys:
        op.create_foreign_key("fk_generation_tasks_retry_of", "generation_tasks", "generation_tasks", ["retry_of_task_id"], ["id"], ondelete="SET NULL")
    foreign_keys = {fk.get("name") for fk in inspect(bind).get_foreign_keys("experiments")}
    if "fk_experiments_created_by" not in foreign_keys:
        op.create_foreign_key("fk_experiments_created_by", "experiments", "users", ["created_by_id"], ["id"], ondelete="SET NULL")

    indexes = {index["name"] for index in inspect(bind).get_indexes("generation_tasks")}
    if "uq_generation_tasks_idempotency_key" not in indexes:
        op.create_index("uq_generation_tasks_idempotency_key", "generation_tasks", ["idempotency_key"], unique=True)
    indexes = {index["name"] for index in inspect(bind).get_indexes("content_documents")}
    if "uq_content_documents_task_id" not in indexes:
        op.create_index("uq_content_documents_task_id", "content_documents", ["task_id"], unique=True)

    duplicates = bind.execute(text("SELECT 1 FROM metric_records GROUP BY product_id, period HAVING COUNT(*) > 1 LIMIT 1")).first()
    indexes = {index["name"] for index in inspect(bind).get_indexes("metric_records")}
    if not duplicates and "uq_metric_product_period" not in indexes:
        op.create_index("uq_metric_product_period", "metric_records", ["product_id", "period"], unique=True)


def downgrade() -> None:
    raise RuntimeError("This baseline migration is intentionally forward-only; restore from backup for rollback")
