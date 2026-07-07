from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=False)

    app_env: str = "development"
    secret_key: str = "dev-secret-key-do-not-use-in-production"
    jwt_private_key_path: str = "./keys/private.pem"
    jwt_public_key_path: str = "./keys/public.pem"
    jwt_algorithm: str = "RS256"
    jwt_access_token_expire_minutes: int = 120
    database_url: str = "sqlite+aiosqlite:///:memory:"
    # Referenced by docker-compose.yml for the db service and to build
    # DATABASE_URL consistently - not read directly elsewhere in app code.
    postgres_password: str = "password"
    redis_url: str = "redis://localhost:6379/0"
    google_client_id: str = "dummy-client-id"
    google_client_secret: str = "dummy-client-secret"
    google_redirect_uri: str = "http://localhost:8000/auth/callback"
    # Base URL used to build signed file-access links returned to the client.
    public_base_url: str = "http://localhost:8000"
    google_api_key: str = ""
    master_encryption_key: str = "dummy-encryption-key-32-bytes-long-x"
    faiss_index_dir: str = "./faiss_indexes"
    arcface_model_path: str = "./models/arcface_r100.onnx"
    retinaface_model_path: str = "./models/retinaface_r50.onnx"
    face_landmarker_model_path: str = "./models/face_landmarker.task"
    antispoofing_model_path: str = "./models/anti_spoof_v1.onnx"
    face_detection_threshold: float = 0.6
    # Thumbnails (~220px) are too small for reliable detection/embedding quality
    # on group or distant shots; always processing the full-resolution file
    # trades indexing speed for materially better recognition recall.
    index_images_from_thumbnails: bool = False
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    rate_limit_scan: str = "5/minute"
    rate_limit_search: str = "10/minute"
    rate_limit_login: str = "10/15minute"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
