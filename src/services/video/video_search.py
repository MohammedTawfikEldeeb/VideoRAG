from typing import Any, Dict, List

from .registry import get_registry, get_table, add_index_to_registry
from ...config import get_settings
from .models import TableMetadata  
from .processor.tools import decode_image

settings = get_settings()


class VideoSearchEngine:

    def __init__(self, video_name: str):
        self.video_index: TableMetadata = get_table(video_name)  
        self.video_name = video_name

    def search_by_speech(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        sims = self.video_index._audio_chunks_obj.chunk_text.similarity(query)  
        results = self.video_index._audio_chunks_obj.select(
            self.video_index._audio_chunks_obj.pos,
            self.video_index._audio_chunks_obj.start_time_sec,
            self.video_index._audio_chunks_obj.end_time_sec,
            similarity=sims,
        ).order_by(sims, asc=False)

        return [
            {
                "start_time": float(entry["start_time_sec"]),
                "end_time": float(entry["end_time_sec"]),
                "similarity": float(entry["similarity"]),
            }
            for entry in results.limit(top_k).collect()
        ]

    def search_by_image(self, image_base64: str, top_k: int) -> List[Dict[str, Any]]:
        image = decode_image(image_base64)
        sims = self.video_index._frames_view_obj.resized_frame.similarity(image)  
        results = self.video_index._frames_view_obj.select(
            self.video_index._frames_view_obj.pos_msec,
            self.video_index._frames_view_obj.resized_frame,
            similarity=sims,
        ).order_by(sims, asc=False)

        return [
            {
                "start_time": entry["pos_msec"] / 1000.0 - settings.DELTA_SECONDS_FRAME_INTERVAL,
                "end_time": entry["pos_msec"] / 1000.0 + settings.DELTA_SECONDS_FRAME_INTERVAL,
                "similarity": float(entry["similarity"]),
            }
            for entry in results.limit(top_k).collect()
        ]

    def search_by_caption(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        sims = self.video_index._frames_view_obj.im_caption.similarity(query)  
        results = self.video_index._frames_view_obj.select(
            self.video_index._frames_view_obj.pos_msec,
            self.video_index._frames_view_obj.im_caption,
            similarity=sims,
        ).order_by(sims, asc=False)

        return [
            {
                "start_time": entry["pos_msec"] / 1000.0 - settings.DELTA_SECONDS_FRAME_INTERVAL,
                "end_time": entry["pos_msec"] / 1000.0 + settings.DELTA_SECONDS_FRAME_INTERVAL,
                "similarity": float(entry["similarity"]),
            }
            for entry in results.limit(top_k).collect()
        ]

    def get_speech_info(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        sims = self.video_index._audio_chunks_obj.chunk_text.similarity(query)  
        results = self.video_index._audio_chunks_obj.select(
            self.video_index._audio_chunks_obj.chunk_text,
            similarity=sims,
        ).order_by(sims, asc=False)

        return [
            {
                "text": entry["chunk_text"],
                "similarity": float(entry["similarity"]),
            }
            for entry in results.limit(top_k).collect()
        ]

    def get_caption_info(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        sims = self.video_index._frames_view_obj.im_caption.similarity(query) 
        results = self.video_index._frames_view_obj.select(
            self.video_index._frames_view_obj.im_caption,
            similarity=sims,
        ).order_by(sims, asc=False)

        return [
            {
                "caption": entry["im_caption"],
                "similarity": float(entry["similarity"]),
            }
            for entry in results.limit(top_k).collect()
        ]