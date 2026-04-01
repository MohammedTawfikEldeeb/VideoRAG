import json
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict

from loguru import logger

from .models import TableMetadata
from ...config import get_settings

logger = logger.bind(name="TableRegistry")
settings = get_settings()
VIDEO_INDEXES_REGISTRY: Dict[str, TableMetadata] = {} 


@lru_cache(maxsize=1)
def get_registry() -> Dict[str, TableMetadata]:
    """Load the video index registry from the latest registry JSON file."""
    global VIDEO_INDEXES_REGISTRY

    if VIDEO_INDEXES_REGISTRY:
        logger.info("Using existing video index registry.")
        return VIDEO_INDEXES_REGISTRY

    try:
        registry_files = [
            f
            for f in os.listdir(settings.RECORDS_DIR)  
            if f.startswith("registry_") and f.endswith(".json")
        ]
        if registry_files:
            latest_file = max(registry_files)
            latest_registry = Path(settings.RECORDS_DIR) / latest_file
            with open(str(latest_registry), "r") as f:
                raw = json.load(f)

            for key, value in raw.items():
                if isinstance(value, str):
                    value = json.loads(value)
                VIDEO_INDEXES_REGISTRY[key] = TableMetadata(**value)  

            logger.info(f"Loaded registry from {latest_registry}")

    except FileNotFoundError:
        logger.warning("Registry file not found. Returning empty registry.")

    return VIDEO_INDEXES_REGISTRY


def add_index_to_registry(
    video_name: str,
    video_cache: str,
    frames_view_name: str,
    audio_view_name: str,
):
    """Register a new video index and save it to a registry JSON file."""
    global VIDEO_INDEXES_REGISTRY

    new_entry = TableMetadata( 
        video_name=video_name,
        video_cache=video_cache,
        video_table=f"{video_cache}.table",
        frames_view=frames_view_name,
        audio_chunks_view=audio_view_name,
    )
    VIDEO_INDEXES_REGISTRY[video_name] = new_entry

    serialized = {
        k: json.loads(v.model_dump_json()) 
        for k, v in VIDEO_INDEXES_REGISTRY.items()
    }

    dtstr = datetime.now().strftime("%Y-%m-%d_%H:%M:%S")  
    records_dir = Path(settings.RECORDS_DIR)  
    records_dir.mkdir(parents=True, exist_ok=True)

    with open(records_dir / f"registry_{dtstr}.json", "w") as f:
        json.dump(serialized, f, indent=4)

    logger.info(f"Video index '{video_name}' registered in the global registry.")


def get_table(video_name: str) -> TableMetadata:
    """Get a single VideoTable from the registry by name."""
    registry = get_registry()
    metadata = registry.get(video_name)

    if metadata is None:
        raise KeyError(f"Video '{video_name}' not found in registry.") 

    if isinstance(metadata, (str, dict)):
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        metadata = TableMetadata(**metadata)  

    logger.info(f"Retrieved table for '{video_name}'")
    return metadata