# Workers Module

The Workers module handles background indexing jobs.

## Contents

- `celery_app.py`: Celery configuration using Redis broker/result backend from settings.
- `indexing_task.py`: Drive folder indexing task that updates event status, lists Drive files, processes image/video bytes in memory, encrypts embeddings, adds vectors to the FAISS index, and publishes Redis progress messages.

## Running

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

The task is designed for mocked Drive/CV/DB collaborators in unit tests and live Redis/PostgreSQL during local Docker runs.
