"""Celery bootstrap and shared model invocation recording."""

from celery import Celery

from ..core.config import get_settings
from ..domain.models import GenerationTask, ModelInvocation


settings = get_settings()
celery_app = Celery("ecommerce_ops", broker=settings.celery_broker_url, backend=settings.celery_result_backend)
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=900,
    task_soft_time_limit=840,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)


def worker_id(task) -> str:
    return str(getattr(getattr(task, "request", None), "id", None) or "local-worker")


def model_for(kind: str) -> str:
    cfg = get_settings()
    return {"image": cfg.image_model, "video": cfg.video_t2v_model}.get(kind, cfg.text_model)


def record_invocation(db, task: GenerationTask, status: str, latency_ms: int, error_code: str | None = None):
    item = ModelInvocation(
        task_id=task.id,
        model=model_for(task.kind),
        modality=task.kind,
        provider_mode=task.provider_mode,
        prompt_version="langgraph-ecommerce-v1",
        schema_version="v1",
        status=status,
        latency_ms=latency_ms,
        error_code=error_code,
    )
    db.add(item)
    return item
