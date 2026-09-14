"""Link AI strategy outputs and establish LangGraph workflow persistence."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20260914_0002"
down_revision = "20260914_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("experiments")}
    if "task_id" not in columns:
        op.add_column("experiments", sa.Column("task_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_experiments_task_id_generation_tasks",
            "experiments",
            "generation_tasks",
            ["task_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_unique_constraint("uq_experiments_task_id", "experiments", ["task_id"])


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("experiments")}
    if "task_id" in columns:
        op.drop_constraint("uq_experiments_task_id", "experiments", type_="unique")
        op.drop_constraint("fk_experiments_task_id_generation_tasks", "experiments", type_="foreignkey")
        op.drop_column("experiments", "task_id")
