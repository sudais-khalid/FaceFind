from typing import List

from pydantic import BaseModel


class ScanRequest(BaseModel):
    frames: List[bytes]


class SearchRequest(BaseModel):
    probe_id: str
    event_code: str


class MatchedFile(BaseModel):
    file_id: str
    score: float
    thumbnail_url: str
    mime_type: str | None = None
    filename: str | None = None


class SearchResponse(BaseModel):
    high_confidence: List[MatchedFile]
    medium_confidence: List[MatchedFile]
    total: int
    search_complete: bool = True


class ScanResponse(SearchResponse):
    probe_id: str
    liveness_score: float
    quality_score: float
