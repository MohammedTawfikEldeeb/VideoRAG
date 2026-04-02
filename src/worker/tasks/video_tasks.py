from celery import states
from celery.exceptions import Ignore
from loguru import logger

from src.services.video.processor.video_processor import VideoProcessor
from src.worker.celery_app import celery_app


@celery_app.task(bind=True, name="src.worker.tasks.video_tasks.process_video")
def process_video(self, video_ref: str, video_name: str) -> dict[str, str]:
    self.update_state(state=states.STARTED, meta={"video_name": video_name})

    try:
        processor = VideoProcessor()
        processor.setup_table(video_name=video_name)
        processor.add_video(video_path=video_ref)
    except Exception as exc:
        logger.exception("Video processing failed for '{}'", video_name)
        self.update_state(state=states.FAILURE, meta={"video_name": video_name, "error": str(exc)})
        raise Ignore() from exc

    return {"video_name": video_name}
