# Drive Module

The Drive module handles organizer Google Drive folder ingestion and attendee-safe file access.

## Contents

- `client.py`: Async Google Drive API wrapper with pagination, retry/backoff, refresh-token retry, download size limits, and temporary media URL generation.
- `router.py`: FastAPI routes for event creation/status, Drive webhook acceptance, public event-code previews, and scoped matched-file URL access.
- `models.py`: Pydantic schemas for Drive/event request and response payloads.

## Running Tests

```bash
python -m pytest tests/unit/test_drive_client.py -q
```

All external Google calls are mocked with `respx`; no live Drive credentials are required.
