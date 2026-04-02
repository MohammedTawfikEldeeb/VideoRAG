"""Celery task exports."""

from src.worker.tasks.video_tasks import process_video

__all__ = ["process_video"]
