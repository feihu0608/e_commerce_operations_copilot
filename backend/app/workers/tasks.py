"""Thin task registry imported by Celery and the outbox dispatcher."""

from .content_tasks import generate_content
from .media_tasks import generate_media, poll_video, submit_video
from .runtime import celery_app

__all__ = ["celery_app", "generate_content", "generate_media", "poll_video", "submit_video"]
