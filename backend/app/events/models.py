from uuid import UUID

from pydantic import BaseModel


class EventDetailResponse(BaseModel):
    event_id: UUID
    organizer_id: UUID
    title: str
    event_code: str
    drive_folder_id: str
    status: str
    files_total: int
    files_indexed: int
    created_at: str | None
    last_indexed_at: str | None


class EventJoinResponse(BaseModel):
    event_id: UUID
    title: str
    organizer_name: str | None
    event_code: str
    files_total: int
    status: str


class ReindexResponse(BaseModel):
    event_id: UUID
    queued: bool


class DeleteEventResponse(BaseModel):
    event_id: UUID
    deleted: bool
