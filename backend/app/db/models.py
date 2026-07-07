from sqlalchemy import Column, String, Integer, BigInteger, Float, DateTime, Boolean, LargeBinary, JSON, ForeignKey, Enum as SQLEnum, func, Uuid
from app.db.database import Base
import uuid
import enum


class User(Base):
    __tablename__ = "users"

    user_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    google_sub = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=func.now())
    last_login = Column(DateTime, nullable=True)
    consent_given = Column(Boolean, default=False)
    consent_at = Column(DateTime, nullable=True)


class EventStatus(str, enum.Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"


class Event(Base):
    __tablename__ = "events"

    event_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organizer_id = Column(Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    title = Column(String(255), nullable=False)
    event_code = Column(String(6), unique=True, nullable=False, index=True)
    drive_folder_id = Column(String(255), nullable=False)
    drive_token_encrypted = Column(LargeBinary, nullable=True)
    faiss_index_path = Column(String(512), nullable=True)
    status = Column(SQLEnum(EventStatus), default=EventStatus.PENDING)
    files_total = Column(Integer, default=0)
    files_indexed = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    last_indexed_at = Column(DateTime, nullable=True)


class DriveFile(Base):
    __tablename__ = "drive_files"

    file_id = Column(String(255), primary_key=True)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("events.event_id"), nullable=False)
    filename = Column(String(512), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    md5_checksum = Column(String(64), nullable=False)
    thumbnail_link = Column(String(2048), nullable=True)
    embedding_count = Column(Integer, default=0)
    quality_flags = Column(JSON, nullable=True)
    indexed_at = Column(DateTime, nullable=True)


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    embedding_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(String(255), ForeignKey("drive_files.file_id"), nullable=False)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("events.event_id"), nullable=False)
    embedding_encrypted = Column(LargeBinary, nullable=False)
    face_index_in_image = Column(Integer, default=0)
    quality_score = Column(Float, nullable=True)
    liveness_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    faiss_id = Column(Integer, nullable=True, unique=True)


class UserProbeEmbedding(Base):
    __tablename__ = "user_probe_embeddings"

    probe_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("events.event_id"), nullable=False)
    embedding_encrypted = Column(LargeBinary, nullable=False)
    liveness_score = Column(Float, nullable=True)
    quality_score = Column(Float, nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)


class SearchResult(Base):
    __tablename__ = "search_results"

    result_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("events.event_id"), nullable=False)
    matched_file_ids = Column(JSON, nullable=False)
    similarity_scores = Column(JSON, nullable=False)
    search_timestamp = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    log_id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    user_id_hash = Column(LargeBinary, nullable=True)
    event_id = Column(Uuid(as_uuid=True), ForeignKey("events.event_id"), nullable=True)
    action = Column(String(64), nullable=False, index=True)
    ip_hash = Column(LargeBinary, nullable=True)
    outcome = Column(String(16), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    chain_hmac = Column(LargeBinary, nullable=False)
