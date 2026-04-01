import base64
import io
from typing import List , Literal , Union
import pixeltable as pxt
from PIL import Image
from pydantic import BaseModel , Field , field_validator , model_validator


class TableMetadata(BaseModel):
    video_name: str = Field(..., description="Name of the video")
    video_cache: str = Field(..., description="Path to the video cache")
    video_table: str = Field(..., description="Video table name")
    frames_view: str = Field(..., description="Frames view name")
    audio_chunks_view: str = Field(..., description="Audio chunks view name")

    _video_table_obj: pxt.Table = None
    _frames_view_obj: pxt.Table = None
    _audio_chunks_obj: pxt.Table = None

    @model_validator(mode="after")
    def resolve_tables(self):
        self._video_table_obj = pxt.get_table(self.video_table)
        self._frames_view_obj = pxt.get_table(self.frames_view)
        self._audio_chunks_obj = pxt.get_table(self.audio_chunks_view)
        return self  

    def __str__(self) -> str:
        return str({
            "video_cache": self.video_cache,
            "video_table": self.video_table,
            "frames_view": self.frames_view,
            "audio_chunks_view": self.audio_chunks_view,
        })

    def describe(self) -> str:
        return f"Video index '{self.video_name}' info: {', '.join(self._video_table_obj.columns)}"  
    

class Base64Image(BaseModel):
    image: str = Field(description="Base64 encoded image string")

    @field_validator("image", mode="before")
    def encode_image(cls, v):
        if isinstance(v, Image.Image):
            buffered = io.BytesIO()
            v.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode("utf-8")
        if isinstance(v, str):
            return v
        raise ValueError(f"Expected PIL Image or base64 string, got {type(v)}")

    def to_pil(self) -> Image.Image:
        return Image.open(io.BytesIO(base64.b64decode(self.image)))


class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageUrlContent(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: str  

    @field_validator("image_url", mode="before")
    def serialize_image(cls, v):
        if isinstance(v, str):
            return f"data:image/jpeg;base64,{v}"
        raise ValueError("Expected a base64 string")


class UserContent(BaseModel):
    role: Literal["user"] = "user"
    content: List[Union[TextContent, ImageUrlContent]]

    @classmethod
    def from_pair(cls, base64_image: str, prompt: str):
        return cls(
            content=[
                ImageUrlContent(image_url=base64_image),  
                TextContent(text=prompt),
            ]
        )