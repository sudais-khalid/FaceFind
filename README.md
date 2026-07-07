# FaceFind

FaceFind is a privacy-first event photo retrieval system. Organizers connect a Google Drive folder, the backend indexes faces into encrypted embeddings and an event-scoped vector index, and attendees scan their face to retrieve only matching media.

## Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Node 20+ for local frontend development
- Google OAuth credentials for live OAuth/Drive usage

## Quick Start

```bash
cp .env.example .env
docker compose up --build
# Open http://localhost:5173
```

On Windows, `start.bat` does this for you (starts Postgres/Redis via Docker,
then the backend and frontend in their own terminal windows) and also works
if you'd rather run the backend/frontend locally instead of in Docker.

For public/shared Google Drive folder indexing during local development, set:

```env
GOOGLE_API_KEY=your-google-cloud-api-key-with-drive-api-enabled
```

## Run Tests

```bash
python -m pytest tests/unit -q
cd frontend
npm.cmd test -- --run
npm.cmd run build
```

## Reindex A Local Event

After setting `GOOGLE_API_KEY`, run:

```bash
export PYTHONPATH=backend   # Windows: set PYTHONPATH=backend
python -m app.scripts.reindex_event EVENT_UUID
python -m app.scripts.diagnose_recall
```

## CV Models

Face detection/landmarking runs on real, locally-executed models, not mocks:

- **Detection + alignment**: MediaPipe `FaceLandmarker` (478-point face mesh; iris landmarks give precise eye centers for alignment). Bundled/downloaded automatically, no manual setup.
- **Recognition**: a real ArcFace ResNet-100 ONNX model, run via `onnxruntime`.

Neither model ships in this repo (both are gitignored - large binaries). Download them into `models/` before indexing/scanning will work:

```bash
mkdir -p models
curl -L -o models/arcface_r100.onnx "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/arcface/model/arcfaceresnet100-8.onnx"
curl -L -o models/face_landmarker.task "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
```

Liveness detection's optional deep anti-spoofing signal degrades gracefully (its weight is redistributed across the other signals) if `ANTISPOOFING_MODEL_PATH` isn't present - it's not required to run the app.

## Architecture

FastAPI exposes auth, event, Drive, scan/search, worker, and health APIs. PostgreSQL stores users, events, Drive file metadata, encrypted embeddings, probes, cached search results, and audit logs. Redis backs Celery, OAuth state, rate limiting, token revocation, and progress messages. FAISS indexes are stored per event on disk with a NumPy fallback for tests. The React/Vite frontend covers attendee join/scan/results and organizer event creation/status sharing.

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the production Docker setup
(`docker-compose.prod.yml`, hardened multi-stage images, CI/CD) - separate
from the dev-oriented `docker-compose.yml` used above.

## Privacy Notes

- Raw face images are processed in memory only.
- Stored embeddings and Drive refresh tokens are AES-256-GCM encrypted.
- File access is scoped through cached search results.
- Audit logs hash user/IP identifiers with a daily salt and HMAC chain.
