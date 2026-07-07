import pytest
from datetime import datetime, timedelta
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))

from app.db.database import Base
from app.db.models import (
    User, Event, DriveFile, FaceEmbedding, UserProbeEmbedding,
    SearchResult, AuditLog, EventStatus
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_create_user(db_session):
    user = User(
        google_sub="test-sub-123",
        email="test@example.com",
        name="Test User",
    )
    db_session.add(user)
    db_session.commit()

    assert user.user_id is not None
    assert user.google_sub == "test-sub-123"
    assert user.consent_given is False


def test_user_unique_google_sub(db_session):
    user1 = User(google_sub="same-sub", email="user1@example.com")
    user2 = User(google_sub="same-sub", email="user2@example.com")

    db_session.add(user1)
    db_session.commit()
    db_session.add(user2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_event(db_session):
    user = User(google_sub="organizer-sub", email="organizer@example.com")
    db_session.add(user)
    db_session.commit()

    event = Event(
        organizer_id=user.user_id,
        title="Test Event",
        event_code="ABC123",
        drive_folder_id="folder-id-123",
        status=EventStatus.PENDING,
    )
    db_session.add(event)
    db_session.commit()

    assert event.event_id is not None
    assert event.status == EventStatus.PENDING
    assert event.files_total == 0
    assert event.files_indexed == 0


def test_event_code_unique(db_session):
    user = User(google_sub="org-sub", email="org@example.com")
    db_session.add(user)
    db_session.commit()

    event1 = Event(
        organizer_id=user.user_id,
        title="Event 1",
        event_code="DUP123",
        drive_folder_id="folder-1",
    )
    event2 = Event(
        organizer_id=user.user_id,
        title="Event 2",
        event_code="DUP123",
        drive_folder_id="folder-2",
    )

    db_session.add(event1)
    db_session.commit()
    db_session.add(event2)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_create_drive_file(db_session):
    user = User(google_sub="sub", email="user@example.com")
    db_session.add(user)
    db_session.flush()  # Generate UUID

    event = Event(
        organizer_id=user.user_id,
        title="Event",
        event_code="EVT001",
        drive_folder_id="folder-123",
    )
    db_session.add(event)
    db_session.flush()

    file = DriveFile(
        file_id="gfile-123",
        event_id=event.event_id,
        filename="photo.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1024000,
        md5_checksum="abc123def456",
    )
    db_session.add(file)
    db_session.commit()

    assert file.embedding_count == 0


def test_create_face_embedding(db_session):
    user = User(google_sub="sub", email="user@example.com")
    db_session.add(user)
    db_session.flush()

    event = Event(
        organizer_id=user.user_id,
        title="Event",
        event_code="EVT001",
        drive_folder_id="folder-123",
    )
    db_session.add(event)
    db_session.flush()

    file = DriveFile(
        file_id="gfile-123",
        event_id=event.event_id,
        filename="photo.jpg",
        mime_type="image/jpeg",
        file_size_bytes=1024000,
        md5_checksum="abc123",
    )
    db_session.add(file)
    db_session.flush()

    embedding = FaceEmbedding(
        file_id=file.file_id,
        event_id=event.event_id,
        embedding_encrypted=b"encrypted-embedding-bytes",
        quality_score=0.95,
    )
    db_session.add(embedding)
    db_session.commit()

    assert embedding.embedding_id is not None
    assert embedding.face_index_in_image == 0


def test_create_user_probe_embedding(db_session):
    user = User(google_sub="sub", email="user@example.com")
    db_session.add(user)
    db_session.flush()

    event = Event(
        organizer_id=user.user_id,
        title="Event",
        event_code="EVT001",
        drive_folder_id="folder-123",
    )
    db_session.add(event)
    db_session.flush()

    probe = UserProbeEmbedding(
        user_id=user.user_id,
        event_id=event.event_id,
        embedding_encrypted=b"encrypted-probe",
        liveness_score=0.98,
        quality_score=0.96,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db_session.add(probe)
    db_session.commit()

    assert probe.probe_id is not None


def test_create_search_result(db_session):
    user = User(google_sub="sub", email="user@example.com")
    db_session.add(user)
    db_session.flush()

    event = Event(
        organizer_id=user.user_id,
        title="Event",
        event_code="EVT001",
        drive_folder_id="folder-123",
    )
    db_session.add(event)
    db_session.flush()

    result = SearchResult(
        user_id=user.user_id,
        event_id=event.event_id,
        matched_file_ids=["file-1", "file-2"],
        similarity_scores=[0.85, 0.75],
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(result)
    db_session.commit()

    assert result.result_id is not None


def test_create_audit_log(db_session):
    log = AuditLog(
        timestamp=datetime.utcnow(),
        action="login",
        outcome="success",
        latency_ms=42,
        chain_hmac=b"chain-hmac-bytes",
    )
    db_session.add(log)
    db_session.commit()

    assert log.log_id is not None
    assert log.action == "login"
