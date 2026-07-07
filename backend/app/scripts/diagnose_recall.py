import asyncio
import json
import os
from collections import defaultdict
from pathlib import Path
from uuid import UUID

import numpy as np
from sqlalchemy import func, select

from app.config import get_settings
from app.db.database import AsyncSessionLocal
from app.db.models import DriveFile, Event, FaceEmbedding, UserProbeEmbedding
from app.search.faiss_index import FAISSIndexManager


def _json_default(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)


async def summarize_events() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        events = (await session.execute(select(Event))).scalars().all()
        print(f"EVENT_COUNT={len(events)}")
        for event in events:
            drive_count = (
                await session.execute(
                    select(func.count()).select_from(DriveFile).where(DriveFile.event_id == event.event_id)
                )
            ).scalar()
            embedding_count = (
                await session.execute(
                    select(func.count()).select_from(FaceEmbedding).where(FaceEmbedding.event_id == event.event_id)
                )
            ).scalar()
            probe_count = (
                await session.execute(
                    select(func.count()).select_from(UserProbeEmbedding).where(UserProbeEmbedding.event_id == event.event_id)
                )
            ).scalar()
            print(
                "EVENT",
                json.dumps(
                    {
                        "event_id": event.event_id,
                        "title": event.title,
                        "event_code": event.event_code,
                        "drive_folder_id": event.drive_folder_id,
                        "has_drive_token": event.drive_token_encrypted is not None,
                        "status": event.status.value if hasattr(event.status, "value") else str(event.status),
                        "files_total": event.files_total,
                        "files_indexed": event.files_indexed,
                        "drive_files": drive_count,
                        "face_embeddings": embedding_count,
                        "probes": probe_count,
                        "faiss_index_path": event.faiss_index_path,
                    },
                    default=_json_default,
                ),
            )

            files = (
                await session.execute(
                    select(DriveFile)
                    .where(DriveFile.event_id == event.event_id)
                    .order_by(DriveFile.filename)
                )
            ).scalars().all()
            missing_indexed_at = [file.filename for file in files if file.indexed_at is None]
            zero_embeddings = [file.filename for file in files if file.embedding_count == 0]
            flagged_files = [
                {"filename": file.filename, "embedding_count": file.embedding_count, "quality_flags": file.quality_flags}
                for file in files
                if file.quality_flags
            ]
            print(
                "INDEXING_COMPLETENESS",
                json.dumps(
                    {
                        "event_id": event.event_id,
                        "drive_file_rows": len(files),
                        "missing_indexed_at_count": len(missing_indexed_at),
                        "missing_indexed_at_samples": missing_indexed_at[:10],
                        "zero_embedding_count": len(zero_embeddings),
                        "zero_embedding_samples": zero_embeddings[:10],
                        "flagged_file_samples": flagged_files[:10],
                    },
                    default=_json_default,
                ),
            )

            faiss_manager = FAISSIndexManager(settings.faiss_index_dir)
            index = faiss_manager.get_or_create_index(str(event.event_id))
            print(
                "FAISS_GAP_CHECK",
                json.dumps(
                    {
                        "event_id": event.event_id,
                        "faiss_ntotal": int(getattr(index, "ntotal", 0)),
                        "face_embedding_rows": int(embedding_count or 0),
                        "matches_postgres": int(getattr(index, "ntotal", 0)) == int(embedding_count or 0),
                    },
                    default=_json_default,
                ),
            )

            probes = (
                await session.execute(
                    select(UserProbeEmbedding)
                    .where(UserProbeEmbedding.event_id == event.event_id)
                    .order_by(UserProbeEmbedding.created_at.desc())
                    .limit(10)
                )
            ).scalars().all()
            for probe in probes:
                print(
                    "PROBE_QUALITY",
                    json.dumps(
                        {
                            "probe_id": probe.probe_id,
                            "user_id": probe.user_id,
                            "liveness_score": probe.liveness_score,
                            "quality_score": probe.quality_score,
                            "created_at": probe.created_at,
                            "expires_at": probe.expires_at,
                        },
                        default=_json_default,
                    ),
                )


if __name__ == "__main__":
    asyncio.run(summarize_events())
