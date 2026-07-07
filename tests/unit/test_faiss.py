import os
import sys
import threading

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.search.faiss_index import FAISSIndexManager


def normalized(seed: int, count: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    vectors = rng.normal(size=(count, 512)).astype(np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def test_search_returns_nearest_neighbors(tmp_path) -> None:
    manager = FAISSIndexManager(str(tmp_path))
    embeddings = normalized(seed=7, count=100)
    ids = list(range(1000, 1100))

    manager.add_embeddings("event-1", embeddings, ids)
    results = manager.search("event-1", embeddings[25], top_k=5, threshold=0.65)

    assert results[0]["id"] == 1025
    assert results[0]["score"] > 0.99


def test_threshold_filters_low_scores(tmp_path) -> None:
    manager = FAISSIndexManager(str(tmp_path))
    embeddings = normalized(seed=11, count=10)

    manager.add_embeddings("event-1", embeddings, list(range(10)))
    results = manager.search("event-1", embeddings[0] * -1, top_k=10, threshold=0.95)

    assert results == []


def test_index_persists_and_reloads(tmp_path) -> None:
    embeddings = normalized(seed=13, count=5)
    first = FAISSIndexManager(str(tmp_path))
    first.add_embeddings("event-1", embeddings, [10, 11, 12, 13, 14])

    second = FAISSIndexManager(str(tmp_path))
    results = second.search("event-1", embeddings[3], top_k=3, threshold=0.65)

    assert results[0]["id"] == 13


def test_delete_index_removes_memory_and_disk_state(tmp_path) -> None:
    manager = FAISSIndexManager(str(tmp_path))
    embeddings = normalized(seed=17, count=3)
    manager.add_embeddings("event-1", embeddings, [1, 2, 3])

    manager.delete_index("event-1")

    assert manager.search("event-1", embeddings[0], top_k=3) == []
    assert not any(tmp_path.iterdir())


def test_concurrent_writes_do_not_corrupt_index(tmp_path) -> None:
    manager = FAISSIndexManager(str(tmp_path))
    batches = [normalized(seed=seed, count=10) for seed in range(20, 24)]

    def add_batch(batch_index: int) -> None:
        start_id = batch_index * 10
        manager.add_embeddings(
            "event-1",
            batches[batch_index],
            list(range(start_id, start_id + 10)),
        )

    threads = [threading.Thread(target=add_batch, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    index = manager.get_or_create_index("event-1")
    assert index.ntotal == 40
