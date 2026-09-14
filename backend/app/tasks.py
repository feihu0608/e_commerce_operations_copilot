"""Thin Celery compatibility entrypoint for existing deployment commands."""

from .workers.tasks import celery_app, generate_content, generate_media, poll_video, submit_video

__all__ = ["celery_app", "generate_content", "generate_media", "poll_video", "submit_video"]
