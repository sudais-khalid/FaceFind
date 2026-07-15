import asyncio
from datetime import datetime
import logging
from typing import Any

import numpy as np
import redis
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.cv_pipeline.pipeline import CVPipeline
from app.db.database import AsyncSessionLocal
from app.db.models import DriveFile, Event, EventStatus, FaceEmbedding
from app.drive.client import DriveClient
from app.search.faiss_index import FAISSIndexManager
from app.security.encryption import derive_key, encrypt_embedding
from app.workers.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)

# Stamped into DriveFile.quality_flags so zero-face results from an older,
# weaker detector are retried after a detector upgrade instead of being
# trusted forever.
DETECTOR_VERSION = "yunet-2023mar"

# Drive downloads overlap (network-bound); CV stays sequential (CPU-bound).
DOWNLOAD_CONCURRENCY = 4
PROCESS_BATCH_SIZE = 8


def _publish_progress(event_id: str, payload: dict[str, Any]) -> None:
    try:
        client = redis.from_url(settings.redis_url)
        client.publish(f"indexing:progress:{event_id}", str(payload))
        client.close()
    except Exception:
        pass


def _is_video(mime_type: str) -> bool:
    return mime_type.startswith("video/")


def _is_image(mime_type: str) -> bool:
    return mime_type.startswith("image/")


async def _next_faiss_id(session) -> int:
    result = await session.execute(select(func.max(FaceEmbedding.faiss_id)))
    current = result.scalar()
    return int(current or 0) + 1


@celery_app.task(bind=True, max_retries=3)
def index_drive_folder(self, event_id: str) -> dict[str, Any]:
    return asyncio.run(_index_drive_folder(event_id, self))


async def _index_drive_folder(event_id: str, task: Any | None = None) -> dict[str, Any]:
    pipeline = CVPipeline()
    index_manager = FAISSIndexManager(settings.faiss_index_dir)
    indexed_faces = 0

    async with AsyncSessionLocal() as session:
        event = await session.get(Event, event_id)
        if event is None:
            return {"event_id": event_id, "status": "missing"}

        event.status = EventStatus.INDEXING
        await session.commit()
        _publish_progress(event_id, {"status": "indexing", "files_indexed": 0})

        try:
            drive_client = DriveClient(
                access_token=None,
                refresh_token_encrypted=event.drive_token_encrypted,
                api_key=settings.google_api_key or None,
            )
            listing = await drive_client.list_files(event.drive_folder_id)
            files = listing.get("files", [])
            event.files_total = len(files)
            event.files_indexed = 0
            await session.commit()

            next_faiss_id = await _next_faiss_id(session)

            # ---- Pass 1: upsert metadata, decide what actually needs work ----
            to_process: list[tuple[dict, DriveFile]] = []
            for file_metadata in files:
                file_id = file_metadata["id"]
                md5_checksum = file_metadata.get("md5Checksum") or ""
                mime_type = file_metadata.get("mimeType") or ""
                existing_result = await session.execute(select(DriveFile).where(DriveFile.file_id == file_id))
                existing = existing_result.scalars().first()
                drive_file = existing or DriveFile(
                    file_id=file_id,
                    event_id=event.event_id,
                    filename=file_metadata.get("name") or file_id,
                    mime_type=mime_type,
                    file_size_bytes=int(file_metadata.get("size") or 0),
                    md5_checksum=md5_checksum,
                    thumbnail_link=file_metadata.get("thumbnailLink"),
                )
                drive_file.event_id = event.event_id
                drive_file.filename = file_metadata.get("name") or drive_file.filename
                drive_file.mime_type = mime_type
                drive_file.file_size_bytes = int(file_metadata.get("size") or 0)
                drive_file.md5_checksum = md5_checksum
                drive_file.thumbnail_link = file_metadata.get("thumbnailLink")
                session.add(drive_file)

                if not (_is_image(mime_type) or _is_video(mime_type)):
                    drive_file.embedding_count = 0
                    drive_file.quality_flags = {"skipped": "unsupported_mime_type"}
                    drive_file.indexed_at = datetime.utcnow()
                    event.files_indexed += 1
                    continue

                # A file is only safe to skip if THIS event already has embeddings
                # for it. Checking the shared DriveFile row alone is not enough:
                # the same Drive folder can be indexed under multiple events (e.g.
                # re-created events, repeated demos), and each event needs its own
                # FaceEmbedding rows encrypted with its own per-event key.
                has_embeddings_for_event = False
                if existing and (existing.embedding_count or 0) > 0:
                    existing_for_event = await session.execute(
                        select(FaceEmbedding.faiss_id)
                        .where(FaceEmbedding.file_id == file_id)
                        .where(FaceEmbedding.event_id == event.event_id)
                        .limit(1)
                    )
                    has_embeddings_for_event = existing_for_event.scalars().first() is not None

                # A prior zero-faces result only counts as "confirmed" if it came
                # from a full-resolution pass with the CURRENT detector. Results
                # from an older/weaker detector (or from tiny thumbnails) must be
                # retried, otherwise detector upgrades never reach files that were
                # unlucky on an earlier pass.
                zero_faces_confirmed = (
                    existing is not None
                    and existing.embedding_count == 0
                    and bool(existing.quality_flags)
                    and str(existing.quality_flags.get("source", "")).startswith("full_download")
                    and existing.quality_flags.get("detector") == DETECTOR_VERSION
                )

                should_skip = (
                    existing is not None
                    and existing.md5_checksum == md5_checksum
                    and existing.indexed_at is not None
                    and (zero_faces_confirmed or has_embeddings_for_event)
                )
                if should_skip:
                    event.files_indexed += 1
                    continue

                to_process.append((file_metadata, drive_file))

            await session.commit()
            _publish_progress(
                event_id,
                {"status": "indexing", "files_total": event.files_total, "files_indexed": event.files_indexed},
            )

            key = derive_key(
                settings.master_encryption_key.encode("utf-8"),
                str(event.organizer_id),
                str(event.event_id),
            )

            download_semaphore = asyncio.Semaphore(DOWNLOAD_CONCURRENCY)

            async def _fetch_media(file_metadata: dict):
                """Download one file's bytes. Returns (bytes, source_flags, exc)."""
                file_id = file_metadata["id"]
                mime_type = file_metadata.get("mimeType") or ""
                async with download_semaphore:
                    try:
                        if (
                            _is_image(mime_type)
                            and settings.index_images_from_thumbnails
                            and file_metadata.get("thumbnailLink")
                        ):
                            try:
                                data = await drive_client.get_thumbnail(file_id, file_metadata["thumbnailLink"])
                                return data, {"source": "thumbnail"}, None
                            except Exception:
                                data = await drive_client.download_file(file_id)
                                return data, {"source": "full_download_after_thumbnail_failure"}, None
                        if _is_image(mime_type):
                            try:
                                data = await drive_client.download_file(file_id)
                                return data, {"source": "full_download"}, None
                            except Exception:
                                # Drive sporadically 403s full downloads, especially
                                # from datacenter IPs. One delayed retry rescues most
                                # of them before degrading quality.
                                await asyncio.sleep(3)
                                try:
                                    data = await drive_client.download_file(file_id)
                                    return data, {"source": "full_download_retry"}, None
                                except Exception:
                                    # Fall back to the thumbnail rather than losing
                                    # the file - a lower-quality embedding beats none.
                                    if not file_metadata.get("thumbnailLink"):
                                        raise
                                    data = await drive_client.get_thumbnail(file_id, file_metadata["thumbnailLink"])
                                    return data, {"source": "thumbnail_after_full_download_failure"}, None
                        data = await drive_client.download_file(file_id)
                        return data, {"source": "full_download"}, None
                    except Exception as exc:
                        return None, None, exc

            # ---- Pass 2: process in batches; downloads overlap via the semaphore
            # while CV/DB work stays sequential (it is CPU-bound anyway). ----
            for start in range(0, len(to_process), PROCESS_BATCH_SIZE):
                batch = to_process[start : start + PROCESS_BATCH_SIZE]
                fetched = await asyncio.gather(*[_fetch_media(fm) for fm, _ in batch])

                for (file_metadata, drive_file), (media_bytes, source_flags, fetch_exc) in zip(batch, fetched):
                    file_id = file_metadata["id"]
                    mime_type = file_metadata.get("mimeType") or ""
                    embeddings_to_index = []
                    try:
                        if fetch_exc is not None:
                            raise fetch_exc

                        # Scoped to this event only: other events sharing the same
                        # Drive file must keep their own embeddings and FAISS entries.
                        old_embeddings = (
                            await session.execute(
                                select(FaceEmbedding.faiss_id)
                                .where(FaceEmbedding.file_id == file_id)
                                .where(FaceEmbedding.event_id == event.event_id)
                                .where(FaceEmbedding.faiss_id.is_not(None))
                            )
                        ).scalars().all()
                        if old_embeddings:
                            index_manager.remove_embeddings(
                                str(event.event_id),
                                [int(faiss_id) for faiss_id in old_embeddings],
                            )
                        await session.execute(
                            delete(FaceEmbedding)
                            .where(FaceEmbedding.file_id == file_id)
                            .where(FaceEmbedding.event_id == event.event_id)
                        )

                        drive_file.quality_flags = dict(source_flags)

                        if _is_video(mime_type):
                            faces = pipeline.process_video(media_bytes)
                        else:
                            faces = pipeline.process_image(media_bytes, mode="indexing")

                            # Thumbnails are tiny (often ~220px wide) and miss faces
                            # in group shots. Retry once against the full-resolution
                            # file before giving up on this image.
                            if not faces and drive_file.quality_flags.get("source") == "thumbnail":
                                full_media_bytes = await drive_client.download_file(file_id)
                                faces = pipeline.process_image(full_media_bytes, mode="indexing")
                                if faces:
                                    drive_file.quality_flags = {"source": "full_download_after_zero_faces"}

                        drive_file.quality_flags["detector"] = DETECTOR_VERSION
                        drive_file.embedding_count = len(faces)
                        if not faces:
                            drive_file.quality_flags["warning"] = "zero_faces_detected"
                        drive_file.indexed_at = datetime.utcnow()

                        faiss_ids = []
                        for face_index, face in enumerate(faces):
                            embedding = face["embedding"]
                            faiss_id = next_faiss_id
                            next_faiss_id += 1
                            embeddings_to_index.append(embedding)
                            faiss_ids.append(faiss_id)
                            quality = face.get("quality") or {}
                            session.add(
                                FaceEmbedding(
                                    file_id=file_id,
                                    event_id=event.event_id,
                                    embedding_encrypted=encrypt_embedding(embedding, key),
                                    face_index_in_image=face_index,
                                    quality_score=float(quality.get("sharpness", 0.0)),
                                    liveness_score=None,
                                    faiss_id=faiss_id,
                                )
                            )

                        if embeddings_to_index:
                            index_manager.add_embeddings(
                                str(event.event_id),
                                np.asarray(embeddings_to_index, dtype=np.float32),
                                faiss_ids,
                            )
                            indexed_faces += len(embeddings_to_index)

                        logger.info("Indexed %s faces from file: %s", len(embeddings_to_index), drive_file.filename)
                    except Exception as file_exc:
                        drive_file.embedding_count = 0
                        drive_file.quality_flags = {"error": type(file_exc).__name__, "message": str(file_exc)[:300]}
                        drive_file.indexed_at = datetime.utcnow()

                    event.files_indexed += 1
                    await session.commit()
                    _publish_progress(
                        event_id,
                        {
                            "status": "indexing",
                            "files_total": event.files_total,
                            "files_indexed": event.files_indexed,
                        },
                    )
                _publish_progress(
                    event_id,
                    {
                        "status": "indexing",
                        "files_total": event.files_total,
                        "files_indexed": event.files_indexed,
                    },
                )

            event.status = EventStatus.READY
            event.last_indexed_at = datetime.utcnow()
            await session.commit()
            _publish_progress(event_id, {"status": "ready", "files_indexed": event.files_indexed})
            return {"event_id": event_id, "status": "ready", "faces_indexed": indexed_faces}
        except Exception as exc:
            event.status = EventStatus.ERROR
            await session.commit()
            _publish_progress(event_id, {"status": "error"})
            if task is not None:
                raise task.retry(exc=exc, countdown=60)
            raise


@celery_app.task
def incremental_reindex(event_id: str, changed_file_ids: list[str]) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "changed_file_ids": changed_file_ids,
        "status": "queued_for_full_reindex",
    }
