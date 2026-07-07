from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.cv_pipeline.pipeline import CVPipeline
from app.db.database import get_db
from app.db.models import DriveFile, Event, EventStatus, FaceEmbedding, SearchResult, User, UserProbeEmbedding
from app.dependencies import get_current_user
from app.search.faiss_index import FAISSIndexManager
from app.search.models import MatchedFile, ScanResponse, SearchRequest, SearchResponse
from app.security.encryption import derive_key, encrypt_embedding

router = APIRouter(prefix="/api", tags=["search"])
settings = get_settings()

_pipeline: CVPipeline | None = None
_index_manager: FAISSIndexManager | None = None


def get_cv_pipeline() -> CVPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = CVPipeline()
    return _pipeline


def get_index_manager() -> FAISSIndexManager:
    global _index_manager
    if _index_manager is None:
        _index_manager = FAISSIndexManager(settings.faiss_index_dir)
    return _index_manager


def _empty_search_response() -> SearchResponse:
    return SearchResponse(high_confidence=[], medium_confidence=[], total=0, search_complete=True)


def _score_to_response_file(drive_file: DriveFile, score: float) -> MatchedFile:
    return MatchedFile(
        file_id=drive_file.file_id,
        score=score,
        thumbnail_url=drive_file.thumbnail_link or "",
        mime_type=drive_file.mime_type,
    )


def _split_search_results(files: list[MatchedFile]) -> tuple[list[MatchedFile], list[MatchedFile]]:
    # Calibrated against measured ArcFace cosine similarity for this pipeline:
    # genuinely different people land ~0.0-0.15, while same-person cross-photo
    # similarity is ~0.7+ for clean shots but can run lower for harder real
    # event photos (blur, angle, distance). Keeping the medium-confidence
    # floor close to the noise ceiling avoids silently dropping real matches.
    high_confidence = [item for item in files if item.score >= 0.55]
    medium_confidence = [item for item in files if 0.40 <= item.score < 0.55]
    return high_confidence, medium_confidence


async def _fetch_drive_files_for_matches(
    db: AsyncSession,
    event_id: UUID,
    faiss_ids: list[int],
) -> dict[int, DriveFile]:
    if not faiss_ids:
        return {}

    result = await db.execute(
        select(FaceEmbedding, DriveFile)
        .join(DriveFile, FaceEmbedding.file_id == DriveFile.file_id)
        .where(FaceEmbedding.event_id == event_id)
        .where(FaceEmbedding.faiss_id.in_(faiss_ids))
    )
    rows = result.all()
    return {int(face.faiss_id): drive_file for face, drive_file in rows if face.faiss_id is not None}


def _build_bucketed_response(
    drive_files_by_faiss_id: dict[int, DriveFile],
    raw_matches: list[dict[str, float | int]],
) -> tuple[list[MatchedFile], list[MatchedFile]]:
    files: list[MatchedFile] = []
    seen_file_ids: set[str] = set()

    for match in raw_matches:
        drive_file = drive_files_by_faiss_id.get(int(match["id"]))
        if drive_file is None or drive_file.file_id in seen_file_ids:
            continue
        seen_file_ids.add(drive_file.file_id)
        files.append(_score_to_response_file(drive_file, float(match["score"])))

    return _split_search_results(files)


async def _store_search_result(
    db: AsyncSession,
    user_id: UUID,
    event_id: UUID,
    matched_files: list[MatchedFile],
) -> None:
    cache = SearchResult(
        user_id=user_id,
        event_id=event_id,
        matched_file_ids=[item.file_id for item in matched_files],
        similarity_scores=[item.score for item in matched_files],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db.add(cache)
    await db.commit()


async def _load_cached_search_response(
    db: AsyncSession,
    user_id: UUID,
    event_id: UUID,
) -> SearchResponse:
    result = await db.execute(
        select(SearchResult)
        .where(SearchResult.user_id == user_id)
        .where(SearchResult.event_id == event_id)
        .where(SearchResult.expires_at > datetime.utcnow())
        .order_by(SearchResult.search_timestamp.desc())
        .limit(1)
    )
    search_result = result.scalars().first()
    if search_result is None:
        return _empty_search_response()

    if not search_result.matched_file_ids:
        return _empty_search_response()

    files_result = await db.execute(
        select(DriveFile).where(DriveFile.file_id.in_(search_result.matched_file_ids))
    )
    drive_files = {item.file_id: item for item in files_result.scalars().all()}

    matched_files: list[MatchedFile] = []
    for file_id, score in zip(search_result.matched_file_ids, search_result.similarity_scores):
        drive_file = drive_files.get(file_id)
        if drive_file is None:
            continue
        matched_files.append(_score_to_response_file(drive_file, float(score)))

    high_confidence, medium_confidence = _split_search_results(matched_files)
    return SearchResponse(
        high_confidence=high_confidence,
        medium_confidence=medium_confidence,
        total=len(high_confidence) + len(medium_confidence),
        search_complete=True,
    )


@router.post("/scan")
async def scan_faces(
    frames: list[UploadFile] = File(...),
    event_code: str = Form(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    pipeline: CVPipeline = Depends(get_cv_pipeline),
    index_manager: FAISSIndexManager = Depends(get_index_manager),
) -> ScanResponse:
    if not 3 <= len(frames) <= 7:
        raise HTTPException(status_code=400, detail="Upload 3 to 7 scan frames")

    event_result = await db.execute(select(Event).where(Event.event_code == event_code.upper()))
    event = event_result.scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.ERROR:
        raise HTTPException(status_code=409, detail="Indexing failed for this event. Ask the organizer to reindex it.")
    if event.status != EventStatus.READY:
        raise HTTPException(status_code=409, detail="Event is not ready yet")

    frame_bytes = [await frame.read() for frame in frames]
    scan_result = pipeline.process_scan_frames(frame_bytes)
    if not scan_result.get("success") or scan_result.get("embedding") is None:
        raise HTTPException(status_code=400, detail=scan_result.get("error") or "Could not verify scan")

    key = derive_key(
        settings.master_encryption_key.encode("utf-8"),
        str(user.user_id),
        str(event.event_id),
    )
    encrypted = encrypt_embedding(scan_result["embedding"], key)
    liveness = scan_result.get("liveness") or {}
    quality = scan_result.get("quality") or {}
    probe = UserProbeEmbedding(
        user_id=user.user_id,
        event_id=event.event_id,
        embedding_encrypted=encrypted,
        liveness_score=float(liveness.get("score", 0.0)),
        quality_score=float(quality.get("sharpness", 0.0)),
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )

    db.add(probe)
    await db.commit()
    await db.refresh(probe)

    raw_matches = index_manager.search(str(event.event_id), scan_result["embedding"], top_k=500, threshold=0.40)
    faiss_ids = [int(match["id"]) for match in raw_matches]
    drive_files_by_faiss_id = await _fetch_drive_files_for_matches(db, event.event_id, faiss_ids)
    high_confidence, medium_confidence = _build_bucketed_response(drive_files_by_faiss_id, raw_matches)

    all_matches = high_confidence + medium_confidence
    await _store_search_result(db, user.user_id, event.event_id, all_matches)

    return ScanResponse(
        probe_id=str(probe.probe_id),
        liveness_score=float(probe.liveness_score or 0.0),
        quality_score=float(probe.quality_score or 0.0),
        search_complete=True,
        high_confidence=high_confidence,
        medium_confidence=medium_confidence,
        total=len(all_matches),
    )


@router.get("/search/results/{probe_id}")
async def get_search_results(
    probe_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    try:
        probe_uuid = UUID(probe_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid probe id")

    probe_result = await db.execute(
        select(UserProbeEmbedding)
        .where(UserProbeEmbedding.probe_id == probe_uuid)
        .where(UserProbeEmbedding.user_id == user.user_id)
        .where(UserProbeEmbedding.expires_at > datetime.utcnow())
    )
    probe = probe_result.scalars().first()
    if probe is None:
        raise HTTPException(status_code=404, detail="Probe not found or expired")

    return await _load_cached_search_response(db, user.user_id, probe.event_id)


@router.post("/search")
async def search_matches(
    request: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    event_result = await db.execute(select(Event).where(Event.event_code == request.event_code.upper()))
    event = event_result.scalars().first()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.status == EventStatus.ERROR:
        raise HTTPException(status_code=409, detail="Indexing failed for this event. Ask the organizer to reindex it.")
    if event.status != EventStatus.READY:
        raise HTTPException(status_code=409, detail="Event is not ready yet")

    try:
        probe_id = UUID(request.probe_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid probe id")

    probe_result = await db.execute(
        select(UserProbeEmbedding)
        .where(UserProbeEmbedding.probe_id == probe_id)
        .where(UserProbeEmbedding.user_id == user.user_id)
        .where(UserProbeEmbedding.event_id == event.event_id)
        .where(UserProbeEmbedding.expires_at > datetime.utcnow())
    )
    probe = probe_result.scalars().first()
    if probe is None:
        raise HTTPException(status_code=404, detail="Probe not found")

    return await _load_cached_search_response(db, user.user_id, event.event_id)
