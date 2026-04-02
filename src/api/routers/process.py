from celery import states
from celery.exceptions import OperationalError
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException, status
from kombu import Connection
from kombu.exceptions import OperationalError as KombuOperationalError
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.config import get_settings
from src.schemas.process import JobStatusResponse, ProcessVideoRequest, ProcessVideoResponse
from src.worker.celery_app import celery_app
from src.worker.tasks.video_tasks import process_video

router = APIRouter(tags=["process"])
settings = get_settings()

STATE_MAPPING = {
    states.PENDING: "pending",
    states.STARTED: "processing",
    states.SUCCESS: "completed",
    states.FAILURE: "failed",
}


def _ensure_task_queue_available() -> None:
    with Connection(settings.CELERY_BROKER_URL, connect_timeout=3) as connection:
        connection.ensure_connection(max_retries=1)

    redis_client = Redis.from_url(settings.CELERY_RESULT_BACKEND)
    redis_client.ping()


@router.post("/video", response_model=ProcessVideoResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_video(payload: ProcessVideoRequest) -> ProcessVideoResponse:
    try:
        _ensure_task_queue_available()
        task = process_video.delay(video_ref=payload.video_ref, video_name=payload.video_name)
        celery_app.backend.store_result(task.id, {"video_name": payload.video_name}, states.PENDING)
    except (ConnectionError, OperationalError, KombuOperationalError, RedisConnectionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task queue is unavailable. Please try again later.",
        ) from exc

    return ProcessVideoResponse(job_id=task.id, status="pending", video_name=payload.video_name)


@router.get("/video/{job_id}", response_model=JobStatusResponse)
async def get_video_job_status(job_id: str) -> JobStatusResponse:
    result = AsyncResult(job_id, app=celery_app)
    metadata = result.info if isinstance(result.info, dict) else {}

    if result.state == states.PENDING and not metadata:
        raise HTTPException(status_code=404, detail="Job not found or result expired.")

    return JobStatusResponse(
        job_id=job_id,
        status=STATE_MAPPING.get(result.state, "pending"),
        video_name=metadata.get("video_name"),
        error=metadata.get("error") if result.state == states.FAILURE else None,
    )
