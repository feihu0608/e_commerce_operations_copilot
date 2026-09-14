import time
from datetime import timedelta

from sqlalchemy import select

from ..core.config import get_settings
from ..core.observability import log_event
from ..domain.models import GenerationTask, ModelInvocation, OutboxEvent, TaskAttempt, utcnow
from ..infrastructure.database import SessionLocal
from ..services.task_runtime import finish_task, record_event
from .tasks import generate_content, generate_media, poll_video, submit_video


def dispatch_once() -> int:
    dispatched = 0
    with SessionLocal() as db:
        events = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.status == "pending", OutboxEvent.next_attempt_at <= utcnow())
            .order_by(OutboxEvent.id)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for event in events:
            try:
                kind = str(event.payload["kind"])
                task_id = int(event.payload["task_id"])
                if kind in {"diagnosis", "creative", "strategy", "review"}:
                    generate_content.delay(task_id, kind)
                elif kind == "video":
                    submit_video.delay(task_id)
                else:
                    generate_media.delay(task_id)
                event.status = "dispatched"
                event.dispatched_at = utcnow()
                event.attempts += 1
                event.last_error = None
                db.commit()
                dispatched += 1
            except Exception as exc:
                db.rollback()
                event = db.get(OutboxEvent, event.id)
                if event:
                    event.attempts += 1
                    event.last_error = str(exc)[:500]
                    event.next_attempt_at = utcnow() + timedelta(seconds=min(60, 2 ** min(event.attempts, 5)))
                    db.commit()
                log_event("outbox_dispatch_failed", event_id=event.id if event else None, error=type(exc).__name__)
    return dispatched


def recover_expired_attempts() -> int:
    recovered = 0
    with SessionLocal() as db:
        attempts = db.scalars(
            select(TaskAttempt)
            .where(TaskAttempt.status == "running", TaskAttempt.lease_expires_at <= utcnow())
            .order_by(TaskAttempt.id)
            .limit(20)
            .with_for_update(skip_locked=True)
        ).all()
        for attempt in attempts:
            task = db.get(GenerationTask, attempt.task_id)
            if not task or task.status != "running":
                attempt.status = "failed"
                attempt.finished_at = utcnow()
                db.commit()
                continue
            if task.kind == "video" and attempt.provider_job_id:
                invocation = db.scalar(
                    select(ModelInvocation)
                    .where(ModelInvocation.task_id == task.id, ModelInvocation.status == "running")
                    .order_by(ModelInvocation.id.desc())
                )
                if invocation:
                    attempt.lease_expires_at = utcnow() + timedelta(seconds=get_settings().task_lease_seconds)
                    record_event(db, task.id, "poll_recovered", attempt_id=attempt.id)
                    db.commit()
                    poll_video.delay(task.id, attempt.id, invocation.id, 0)
                    recovered += 1
                    continue
            finish_task(
                db,
                task.id,
                attempt.id,
                "failed",
                error_code="WORKER_LEASE_EXPIRED",
                error_message="Worker 心跳租约过期，请人工重试；未自动重复提交可能计费的模型任务",
            )
            recovered += 1
    return recovered


def run():
    settings = get_settings()
    log_event("outbox_dispatcher_started")
    while True:
        recover_expired_attempts()
        dispatch_once()
        time.sleep(settings.outbox_poll_seconds)


if __name__ == "__main__":
    run()
