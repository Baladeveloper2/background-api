import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "worker",
    broker="memory://",
    backend="rpc://"
)

celery_app.conf.task_routes = {
    "app.worker.generate_case_pdf": "pdf-queue",
    "app.worker.merge_check_documents": "pdf-queue"
}

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Kolkata',
    enable_utc=True,
)
