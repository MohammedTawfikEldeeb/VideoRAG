
from pydantic import BaseModel, Field


class ProcessVideoRequest(BaseModel):
    video_ref: str = Field(..., min_length=1)
    video_name: str = Field(..., min_length=1)


class ProcessVideoResponse(BaseModel):
    job_id: str
    status: str
    video_name: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    video_name: str | None = None
    error: str | None = None
