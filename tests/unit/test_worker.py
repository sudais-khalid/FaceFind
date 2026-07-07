import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.workers.celery_app import celery_app
from app.workers.indexing_task import incremental_reindex


def test_celery_worker_configuration() -> None:
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_expires == 3600
    assert celery_app.conf.worker_max_tasks_per_child == 50


def test_incremental_reindex_returns_queued_status() -> None:
    result = incremental_reindex.run("event-1", ["file-1"])

    assert result["event_id"] == "event-1"
    assert result["changed_file_ids"] == ["file-1"]
    assert result["status"] == "queued_for_full_reindex"
