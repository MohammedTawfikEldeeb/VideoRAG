from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    APP_VERSION: str = "0.1.0"

    # --- OpenRouter Configuration ---
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # --- Groq Configuration (audio transcription) ---
    GROQ_API_KEY: str
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    AUDIO_TRANSCRIPT_MODEL: str = "whisper-large-v3"

    # --- Vision / Captioning Model ---
    IMAGE_CAPTION_MODEL: str = "openai/gpt-4o-mini"

    # --- Video Ingestion Configuration ---
    SPLIT_FRAMES_COUNT: int = 45
    AUDIO_CHUNK_LENGTH: int = 10
    AUDIO_OVERLAP_SECONDS: int = 1
    AUDIO_MIN_CHUNK_DURATION_SECONDS: int = 1

    # --- Transcription Similarity Search Configuration ---
    TRANSCRIPT_SIMILARITY_EMBD_MODEL: str = "openai/text-embedding-3-small"

    # --- Image Similarity Search Configuration ---
    IMAGE_SIMILARITY_EMBD_MODEL: str = "openai/clip-vit-base-patch32"

    # --- Image Captioning Configuration ---
    IMAGE_RESIZE_WIDTH: int = 1024
    IMAGE_RESIZE_HEIGHT: int = 768
    CAPTION_SIMILARITY_EMBD_MODEL: str = "openai/text-embedding-3-small"

    # --- Caption Similarity Search Configuration ---
    CAPTION_MODEL_PROMPT: str = "Describe what is happening in the image"
    DELTA_SECONDS_FRAME_INTERVAL: float = 5.0

    # --- Video Search Engine Configuration ---
    VIDEO_CLIP_SPEECH_SEARCH_TOP_K: int = 1
    VIDEO_CLIP_CAPTION_SEARCH_TOP_K: int = 1
    VIDEO_CLIP_IMAGE_SEARCH_TOP_K: int = 1
    QUESTION_ANSWER_TOP_K: int = 3

    # --- Opik Observability Configuration ---
    OPIK_API_KEY: str = ""
    OPIK_WORKSPACE: str = "default"
    OPIK_PROJECT: str = "AgenticVideoRAG"

    # --- Volume / Directory Paths ---
    VIDEOS_DIR: str = "videos"
    CLIPS_DIR: str = "clips"
    RECORDS_DIR: str = ".records"
    CONVERSATIONS_DB_URL: str = "sqlite+aiosqlite:///./data/conversations.db"

    # --- API Configuration ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # --- Celery Configuration ---
    CELERY_BROKER_URL: str = "amqp://guest:guest@localhost:5672//"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # --- LangGraph Agent Configuration ---
    MEMORY_DB_PATH: str = "./data/memory.db"
    AGENT_MODEL: str = "openai/gpt-4o-mini"
    ROUTER_MODEL: str = "openai/gpt-4o-mini"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()
