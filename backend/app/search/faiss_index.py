from __future__ import annotations

import os
import pickle
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

try:
    import faiss  # type: ignore
except Exception:
    faiss = None


class NumpyIndex:
    """Small FAISS-compatible fallback used when faiss-cpu is unavailable."""

    def __init__(self, dimension: int = 512):
        self.dimension = dimension
        self.embeddings = np.empty((0, dimension), dtype=np.float32)
        self.ids = np.empty((0,), dtype=np.int64)

    @property
    def ntotal(self) -> int:
        return int(self.ids.shape[0])

    def add_with_ids(self, embeddings: np.ndarray, ids: np.ndarray) -> None:
        self.embeddings = np.vstack([self.embeddings, embeddings.astype(np.float32)])
        self.ids = np.concatenate([self.ids, ids.astype(np.int64)])

    def search(self, probe: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
        if self.ntotal == 0:
            scores = np.full((1, top_k), -1.0, dtype=np.float32)
            ids = np.full((1, top_k), -1, dtype=np.int64)
            return scores, ids

        similarities = np.dot(self.embeddings, probe.reshape(-1).astype(np.float32))
        order = np.argsort(similarities)[::-1][:top_k]
        scores = similarities[order].astype(np.float32)
        ids = self.ids[order].astype(np.int64)

        if len(order) < top_k:
            pad = top_k - len(order)
            scores = np.concatenate([scores, np.full((pad,), -1.0, dtype=np.float32)])
            ids = np.concatenate([ids, np.full((pad,), -1, dtype=np.int64)])

        return scores.reshape(1, -1), ids.reshape(1, -1)

    def remove_ids(self, ids_to_remove: np.ndarray) -> int:
        remove_set = set(int(item) for item in ids_to_remove.tolist())
        keep_mask = np.array([int(item) not in remove_set for item in self.ids], dtype=bool)
        removed = int(np.count_nonzero(~keep_mask))
        self.embeddings = self.embeddings[keep_mask]
        self.ids = self.ids[keep_mask]
        return removed


class FAISSIndexManager:
    """Manage event-scoped vector indexes with disk persistence."""

    def __init__(self, index_dir: str, max_cached_indexes: int = 10):
        self.index_dir = Path(index_dir)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.max_cached_indexes = max_cached_indexes
        self.indexes: OrderedDict[str, Any] = OrderedDict()
        self.locks: dict[str, threading.RLock] = {}

    def _index_path(self, event_id: str) -> Path:
        suffix = ".index" if faiss is not None else ".pkl"
        return self.index_dir / f"{event_id}{suffix}"

    def get_lock(self, event_id: str) -> threading.RLock:
        """Get or create the write lock for an event index."""
        if event_id not in self.locks:
            self.locks[event_id] = threading.RLock()
        return self.locks[event_id]

    def _create_index(self) -> Any:
        if faiss is None:
            return NumpyIndex()
        base_index = faiss.IndexFlatIP(512)
        return faiss.IndexIDMap(base_index)

    def _load_index(self, event_id: str) -> Any:
        path = self._index_path(event_id)
        if not path.exists():
            return self._create_index()

        if faiss is not None:
            return faiss.read_index(str(path))

        with path.open("rb") as handle:
            return pickle.load(handle)

    def _save_index(self, event_id: str, index: Any) -> None:
        path = self._index_path(event_id)
        if faiss is not None:
            faiss.write_index(index, str(path))
            return

        with path.open("wb") as handle:
            pickle.dump(index, handle)

    def get_or_create_index(self, event_id: str) -> Any:
        """Load an event index from disk or create a new one."""
        if event_id in self.indexes:
            self.indexes.move_to_end(event_id)
            return self.indexes[event_id]

        index = self._load_index(event_id)
        self.indexes[event_id] = index
        self.indexes.move_to_end(event_id)

        while len(self.indexes) > self.max_cached_indexes:
            self.indexes.popitem(last=False)

        return index

    @staticmethod
    def _normalize(embeddings: np.ndarray) -> np.ndarray:
        array = np.asarray(embeddings, dtype=np.float32)
        if array.ndim == 1:
            array = array.reshape(1, -1)
        norms = np.linalg.norm(array, axis=1, keepdims=True)
        return array / np.maximum(norms, 1e-12)

    def add_embeddings(
        self,
        event_id: str,
        embeddings: np.ndarray,
        ids: list[int],
    ) -> None:
        """Add L2-normalized embeddings and persist the event index."""
        if len(ids) == 0:
            return

        normalized = self._normalize(embeddings)
        if normalized.shape[0] != len(ids):
            raise ValueError("Number of embeddings must match number of ids")
        if normalized.shape[1] != 512:
            raise ValueError("Face embeddings must be 512-dimensional")

        with self.get_lock(event_id):
            index = self.get_or_create_index(event_id)
            np_ids = np.asarray(ids, dtype=np.int64)
            index.add_with_ids(normalized.astype(np.float32), np_ids)
            self._save_index(event_id, index)

    def search(
        self,
        event_id: str,
        probe_embedding: np.ndarray,
        top_k: int = 500,
        threshold: float = 0.40,
    ) -> list[dict[str, float | int]]:
        """Search one event index and return matches with raw similarity scores."""
        if top_k <= 0:
            return []

        index = self.get_or_create_index(event_id)
        if getattr(index, "ntotal", 0) == 0:
            return []

        probe = self._normalize(probe_embedding)
        scores, ids = index.search(probe.astype(np.float32), top_k)

        results: list[dict[str, float | int]] = []
        for faiss_id, score in zip(ids[0], scores[0]):
            if int(faiss_id) < 0:
                continue
            score_float = float(score)
            if score_float >= threshold:
                results.append({"id": int(faiss_id), "score": score_float})

        return sorted(results, key=lambda item: float(item["score"]), reverse=True)

    def remove_embeddings(self, event_id: str, ids: list[int]) -> None:
        """Remove embeddings by FAISS integer ID and persist the index."""
        if not ids:
            return

        with self.get_lock(event_id):
            index = self.get_or_create_index(event_id)
            selector_ids = np.asarray(ids, dtype=np.int64)
            if faiss is not None:
                selector = faiss.IDSelectorBatch(selector_ids.size, faiss.swig_ptr(selector_ids))
                index.remove_ids(selector)
            else:
                index.remove_ids(selector_ids)
            self._save_index(event_id, index)

    def delete_index(self, event_id: str) -> None:
        """Delete an event index from memory and disk."""
        with self.get_lock(event_id):
            self.indexes.pop(event_id, None)
            for suffix in (".index", ".pkl"):
                path = self.index_dir / f"{event_id}{suffix}"
                if path.exists():
                    os.remove(path)
