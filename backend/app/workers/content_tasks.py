"""Celery task adapter for the four bounded LangGraph workflows."""

import time

from sqlalchemy import func, select

from ..core.config import get_settings
from ..domain.models import ContentDocument, Experiment, GenerationTask
from ..infrastructure.database import SessionLocal
from ..integrations.siliconflow import SiliconFlowGateway
from ..services.task_runtime import claim_task, extend_attempt_lease, finish_task, record_event
from ..workflows.checkpoint import workflow_checkpointer
from ..workflows.graph import run_generation_workflow
from ..workflows.state import GenerationState, WorkflowContext
from .runtime import celery_app, record_invocation, worker_id


def persist_workflow_output(db, task: GenerationTask, state: GenerationState) -> str:
    payload = state["candidate"]
    if payload is None:
        raise ValueError("validated workflow output is required")
    if task.kind == "strategy":
        item = Experiment(
            product_id=task.product_id,
            task_id=task.id,
            title=f"{task.input_snapshot['name']} AI 投放建议",
            status="draft",
            strategy={
                "audience": payload["audience"],
                "channel": payload["channel"],
                "budget": payload["budget"],
                "period": payload["period"],
                "creative_angle": payload["creative_angle"],
                "targets": {"ctr": payload["target_ctr"], "stop_roas": payload["stop_roas"]},
                "rationale": payload["rationale"],
                "provider_mode": task.provider_mode,
            },
        )
        db.add(item)
        db.flush()
        return f"experiment:{item.id}"
    revision = int(
        db.scalar(
            select(func.max(ContentDocument.revision)).where(
                ContentDocument.product_id == task.product_id,
                ContentDocument.content_type == task.kind,
            )
        )
        or 0
    ) + 1
    item = ContentDocument(product_id=task.product_id, task_id=task.id, content_type=task.kind, payload=payload, revision=revision)
    db.add(item)
    db.flush()
    return f"content:{item.id}:revision:{revision}"


@celery_app.task(name="generate_content", bind=True)
def generate_content(self, task_id: int, content_type: str):
    started = time.perf_counter()
    with SessionLocal() as db:
        attempt = claim_task(db, task_id, worker_id(self))
        if not attempt:
            return
        task = db.get(GenerationTask, task_id)
        try:
            extend_attempt_lease(
                db,
                task.id,
                attempt.id,
                get_settings().text_workflow_lease_seconds,
                "bounded_langgraph_model_calls",
            )
            initial_state: GenerationState = {
                "task_id": task.id,
                "attempt_id": attempt.id,
                "product_id": task.product_id,
                "workflow_kind": content_type,
                "provider_mode": task.provider_mode,
                "input_snapshot": task.input_snapshot,
                "prompt_version": "langgraph-ecommerce-v1",
                "schema_version": "v1",
                "evidence_refs": [],
                "candidate": None,
                "validation_errors": [],
                "repair_count": 0,
                "max_repairs": 1,
                "output_revision_id": None,
                "workflow_status": "running",
                "node_trace": [],
            }
            context = WorkflowContext(gateway=SiliconFlowGateway(), persist=lambda state: persist_workflow_output(db, task, state))
            with workflow_checkpointer() as checkpointer:
                result = run_generation_workflow(initial_state, context, checkpointer)
            record_event(
                db,
                task.id,
                "langgraph_completed",
                attempt_id=attempt.id,
                thread_id=f"task:{task.id}:attempt:{attempt.id}",
                workflow=content_type,
                node_trace=result.get("node_trace", []),
                repair_count=result.get("repair_count", 0),
                output_revision_id=result.get("output_revision_id"),
            )
            if result.get("workflow_status") != "succeeded":
                raise ValueError("; ".join(result.get("validation_errors") or ["LangGraph output validation failed"]))
            record_invocation(db, task, "succeeded", int((time.perf_counter() - started) * 1000))
            finish_task(db, task.id, attempt.id, "succeeded")
        except Exception as exc:
            db.rollback()
            task = db.get(GenerationTask, task_id)
            if task:
                record_invocation(db, task, "failed", int((time.perf_counter() - started) * 1000), type(exc).__name__)
            detail = str(exc).strip() or type(exc).__name__
            finish_task(db, task_id, attempt.id, "failed", error_code=type(exc).__name__, error_message=f"模型调用或输出校验失败：{detail[:240]}")
