"""LangChain tool wrappers for VideoRAG agent."""

from langchain_core.tools import tool

from src.services.video.processor.tools import extract_video_clip
from src.services.video.processor.video_processor import VideoProcessor
from src.services.video import VideoSearchEngine
from src.config import get_settings
from pathlib import Path
from uuid import uuid4
from loguru import logger

logger = logger.bind(name="AgentTools")
settings = get_settings()
video_processor = VideoProcessor()

# Ensure clips output directory exists
Path(settings.CLIPS_DIR).mkdir(parents=True, exist_ok=True)


@tool
def process_video(video_path: str) -> str:
    """Process a video file and prepare it for searching.

    Args:
        video_path: Path to the video file to process.

    Returns:
        Success message indicating the video was processed.
    """
    exists = video_processor._check_if_exists(video_path)
    if exists:
        logger.info(f"Video index for '{video_path}' already exists and is ready for use.")
        return f"Video '{video_path}' already indexed and ready"
    video_processor.setup_table(video_name=video_path)
    is_done = video_processor.add_video(video_path=video_path)
    return f"Video '{video_path}' processed successfully" if is_done else f"Failed to process '{video_path}'"


@tool
def get_video_clip_from_user_query(video_path: str, user_query: str) -> str:
    """Get a video clip based on the user query using speech and caption similarity.

    Args:
        video_path: The path to the video file.
        user_query: The user query to search for.

    Returns:
        Path to the extracted video clip.
    """
    search_engine = VideoSearchEngine(video_path)

    speech_clips = search_engine.search_by_speech(user_query, settings.VIDEO_CLIP_SPEECH_SEARCH_TOP_K)
    caption_clips = search_engine.search_by_caption(user_query, settings.VIDEO_CLIP_CAPTION_SEARCH_TOP_K)

    speech_sim = speech_clips[0]["similarity"] if speech_clips else 0
    caption_sim = caption_clips[0]["similarity"] if caption_clips else 0

    video_clip_info = speech_clips[0] if speech_sim > caption_sim else caption_clips[0]

    video_clip = extract_video_clip(
        video_path=video_path,
        start_time=video_clip_info["start_time"],
        end_time=video_clip_info["end_time"],
        output_path=f"{settings.CLIPS_DIR}/{str(uuid4())}.mp4",
    )

    return video_clip.filename


@tool
def get_video_clip_from_image(video_path: str, user_image: str) -> str:
    """Get a video clip based on similarity to a provided image.

    Args:
        video_path: The path to the video file.
        user_image: The query image encoded in base64 format.

    Returns:
        Path to the extracted video clip.
    """
    search_engine = VideoSearchEngine(video_path)
    image_clips = search_engine.search_by_image(user_image, settings.VIDEO_CLIP_IMAGE_SEARCH_TOP_K)

    video_clip = extract_video_clip(
        video_path=video_path,
        start_time=image_clips[0]["start_time"],
        end_time=image_clips[0]["end_time"],
        output_path=f"{settings.CLIPS_DIR}/{str(uuid4())}.mp4",
    )

    return video_clip.filename


@tool
def ask_question_about_video(video_path: str, user_query: str) -> str:
    """Get relevant captions from the video based on the user's question.

    Args:
        video_path: The path to the video file.
        user_query: The question to search for relevant captions.

    Returns:
        Concatenated relevant captions from the video.
    """
    search_engine = VideoSearchEngine(video_path)
    caption_info = search_engine.get_caption_info(user_query, settings.QUESTION_ANSWER_TOP_K)

    answer = "\n".join(entry["caption"] for entry in caption_info)
    return answer
