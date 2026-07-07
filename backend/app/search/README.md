# Search Module

The Search module owns event-scoped vector retrieval for face embeddings.

## Contents

- `faiss_index.py`: Disk-backed vector index manager. It uses `faiss.IndexIDMap(IndexFlatIP)` when `faiss-cpu` is installed and falls back to a compatible NumPy index for unit tests or minimal environments.
- `router.py`: FastAPI routes for `/api/scan` and `/api/search`, including probe encryption, liveness-gated scan handling, FAISS lookup, result caching, and duplicate file collapse.
- `models.py`: Pydantic schemas for scan/search payloads and matched file responses.

## Running Tests

```bash
python -m pytest tests/unit/test_faiss.py -q
```

Embeddings are expected to be 512-dimensional float vectors. They are normalized before insertion and search so inner product behaves as cosine similarity.
