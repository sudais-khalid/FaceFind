from pydantic import BaseModel
from uuid import UUID
from typing import Optional


class CreateEventRequest(BaseModel):
    title: str
    drive_folder_url: str


class EventStatusResponse(BaseModel):
    status: str
    files_total: int
    files_indexed: int
    last_indexed_at: Optional[str]


class CreateEventResponse(BaseModel):
    event_id: UUID
    event_code: str
    status: str


class FileUrlResponse(BaseModel):
    url: str
    expires_in: int


class DriveWebhookResponse(BaseModel):
    accepted: bool
