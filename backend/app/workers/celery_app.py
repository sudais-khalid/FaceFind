from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "facefind",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.indexing_task"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=3600,
    worker_max_tasks_per_child=50,
    timezone="UTC",
)
