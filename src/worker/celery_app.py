from celery import Celery

from src.config import get_settings

settings = get_settings()

celery_app = Celery(
    "videorag",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["src.worker.tasks.video_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_default_queue="video_processing",
    result_expires=86400,
)
