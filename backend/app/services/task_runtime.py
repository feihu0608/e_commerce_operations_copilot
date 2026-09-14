from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.observability import current_request_id
from ..domain.models import AuditLog, Competitor, ContentDocument, Experiment, GenerationTask, MetricRecord, OutboxEvent, Product, TaskAttempt, TaskEvent, utcnow


TERMINAL_STATUSES = {"succeeded", "failed", "timeout", "cancelled"}


def _workflow_input_snapshot(db: Session, product: Product, kind: str) -> dict:
    snapshot = {
        "product_id": product.id,
        "name": product.name,
        "category": product.category,
        "price": str(product.price),
        "summary": product.summary,
    }
    if kind == "diagnosis":
        competitors = db.scalars(select(Competitor).where(Competitor.product_id == product.id).order_by(Competitor.id)).all()
        snapshot["competitors"] = [
            {"name": item.name, "price": str(item.price), "highlights": item.highlights}
            for item in competitors
        ]
    if kind in {"creative", "strategy"}:
        content_types = ["diagnosis"] if kind == "creative" else ["diagnosis", "creative"]
        documents = db.scalars(
            select(ContentDocument)
            .where(ContentDocument.product_id == product.id, ContentDocument.content_type.in_(content_types))
            .order_by(ContentDocument.id.desc())
        ).all()
        latest: dict[str, dict] = {}
        for document in documents:
            latest.setdefault(document.content_type, document.payload)
        snapshot["confirmed_inputs"] = latest
    if kind == "review":
        metric = db.scalar(select(MetricRecord).where(MetricRecord.product_id == product.id).order_by(MetricRecord.id.desc()))
        experiment = db.scalar(
            select(Experiment)
            .where(Experiment.product_id == product.id, Experiment.status == "approved")
            .order_by(Experiment.id.desc())
        )
        if metric:
            ctr = round(metric.clicks / metric.impressions * 100, 2) if metric.impressions else None
            conversion_rate = round(metric.paid_orders / metric.clicks * 100, 2) if metric.clicks else None
            roas = round(float(metric.gmv / metric.ad_spend), 2) if metric.ad_spend else None
            snapshot["actual_metrics"] = {
                "period": metric.period,
                "impressions": metric.impressions,
                "clicks": metric.clicks,
                "paid_orders": metric.paid_orders,
                "gmv": float(metric.gmv),
                "ad_spend": float(metric.ad_spend),
                "ctr": ctr,
                "conversion_rate": conversion_rate,
                "roas": roas,
            }
        snapshot["approved_strategy"] = experiment.strategy if experiment else None
    return snapshot


def record_event(db: Session, task_id: int, event_type: str, **payload) -> TaskEvent:
    event = TaskEvent(task_id=task_id, event_type=event_type, payload=payload)
    db.add(event)
    return event


def record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: int | str,
    actor_id: int | None = None,
    **detail,
) -> AuditLog:
    item = AuditLog(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        request_id=current_request_id(),
        detail=detail,
    )
    db.add(item)
    return item


def create_generation_task(
    db: Session,
    product_id: int,
    kind: str,
    title: str,
    provider_mode: str,
    actor_id: int | None,
    idempotency_key: str | None = None,
    retry_of_task_id: int | None = None,
) -> tuple[GenerationTask, bool]:
    if idempotency_key:
        existing = db.scalar(select(GenerationTask).where(GenerationTask.idempotency_key == idempotency_key))
        if existing:
            return existing, False
    product = db.get(Product, product_id)
    if not product:
        raise LookupError("商品不存在")
    task = GenerationTask(
        product_id=product_id,
        retry_of_task_id=retry_of_task_id,
        kind=kind,
        title=title,
        provider_mode=provider_mode,
        idempotency_key=idempotency_key,
        request_id=current_request_id(),
        input_snapshot=_workflow_input_snapshot(db, product, kind),
    )
    db.add(task)
    db.flush()
    outbox = OutboxEvent(
        event_key=f"generation-task:{task.id}:created:{uuid4().hex}",
        aggregate_type="generation_task",
        aggregate_id=task.id,
        event_type="generation_task.created",
        payload={"task_id": task.id, "kind": task.kind},
    )
    db.add(outbox)
    record_event(db, task.id, "created", status="pending", provider_mode=provider_mode)
    record_audit(db, "generation_task.create", "generation_task", task.id, actor_id, kind=kind)
    db.commit()
    db.refresh(task)
    return task, True


def claim_task(db: Session, task_id: int, worker_id: str) -> TaskAttempt | None:
    task = db.scalar(select(GenerationTask).where(GenerationTask.id == task_id).with_for_update())
    if not task or task.status != "pending":
        return None
    attempt_no = int(db.scalar(select(func.count()).select_from(TaskAttempt).where(TaskAttempt.task_id == task_id)) or 0) + 1
    attempt = TaskAttempt(
        task_id=task.id,
        attempt_no=attempt_no,
        worker_id=worker_id,
        lease_expires_at=utcnow() + timedelta(seconds=get_settings().task_lease_seconds),
    )
    task.status = "running"
    task.progress = 5
    task.version += 1
    db.add(attempt)
    record_event(db, task.id, "started", attempt_no=attempt_no, worker_id=worker_id)
    db.commit()
    db.refresh(attempt)
    return attempt


def update_progress(db: Session, task_id: int, attempt_id: int, progress: int, event_type: str = "progress") -> bool:
    task = db.scalar(select(GenerationTask).where(GenerationTask.id == task_id).with_for_update())
    attempt = db.get(TaskAttempt, attempt_id)
    if not task or not attempt or task.status != "running" or attempt.status != "running":
        return False
    task.progress = max(task.progress, min(progress, 99))
    attempt.lease_expires_at = utcnow() + timedelta(seconds=get_settings().task_lease_seconds)
    record_event(db, task_id, event_type, attempt_id=attempt_id, progress=task.progress)
    db.commit()
    return True


def finish_task(
    db: Session,
    task_id: int,
    attempt_id: int,
    status: str,
    *,
    result_url: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> bool:
    if status not in TERMINAL_STATUSES:
        raise ValueError("finish status must be terminal")
    task = db.scalar(select(GenerationTask).where(GenerationTask.id == task_id).with_for_update())
    attempt = db.get(TaskAttempt, attempt_id)
    if not task or not attempt or task.status != "running" or attempt.status != "running":
        return False
    task.status = status
    task.progress = 100
    task.result_url = result_url
    task.error_message = error_message
    task.version += 1
    attempt.status = status
    attempt.error_code = error_code
    attempt.error_message = error_message
    attempt.finished_at = utcnow()
    record_event(db, task_id, status, attempt_id=attempt_id, error_code=error_code, result_url=result_url)
    db.commit()
    return True
