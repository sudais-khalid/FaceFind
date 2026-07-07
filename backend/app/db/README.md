# Module 1 — Database Models & Migrations

## Overview

Defines all SQLAlchemy ORM models and Alembic migrations for the FaceFind application.

## Models

- **User**: Google OAuth identity, consent tracking
- **Event**: Photo event with organizer, status tracking, indexing progress
- **DriveFile**: Google Drive file metadata with embedding tracking
- **FaceEmbedding**: Encrypted face vectors extracted from files, FAISS-mapped
- **UserProbeEmbedding**: User's scanned face embedding (24h TTL)
- **SearchResult**: Cached search results (30min TTL)
- **AuditLog**: Tamper-evident activity log with HMAC chain

## Running Migrations

```bash
# Upgrade to latest
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "description"

# Downgrade
alembic downgrade -1
```

## Testing

```bash
pytest tests/unit/test_models.py -v
```

All models use generic `Uuid` type for compatibility with SQLite (dev) and PostgreSQL (prod).
