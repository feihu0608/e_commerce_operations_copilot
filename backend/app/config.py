from functools import lru_cache
from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    app_secret_key: str = os.getenv("APP_SECRET_KEY", "dev-only-change-me")
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://ecommerce_ops:ecommerce_ops_dev@localhost:5432/ecommerce_ops",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
    siliconflow_base_url: str = os.getenv("SILICONFLOW_BASE_URL", "https://api.siliconflow.cn/v1")
    siliconflow_api_key: str = os.getenv("SILICONFLOW_API_KEY", "")
    text_model: str = os.getenv("TEXT_MODEL", "Qwen/Qwen3.6-27B")
    analysis_model: str = os.getenv("ANALYSIS_MODEL", "deepseek-ai/DeepSeek-V3.2")
    image_model: str = os.getenv("IMAGE_MODEL", "Kwai-Kolors/Kolors")
    video_i2v_model: str = os.getenv("VIDEO_I2V_MODEL", "Wan-AI/Wan2.2-I2V-A14B")
    video_t2v_model: str = os.getenv("VIDEO_T2V_MODEL", "Wan-AI/Wan2.2-T2V-A14B")
    vision_model: str = os.getenv("VISION_MODEL", "Qwen/Qwen2.5-VL-72B-Instruct")
    ai_mode: str = os.getenv("AI_MODE", "mock")
    media_mode: str = os.getenv("MEDIA_MODE", "mock")
    storage_dir: str = os.getenv("STORAGE_DIR", "/app/storage")
    demo_operator_password: str = os.getenv("DEMO_OPERATOR_PASSWORD", "")
    demo_manager_password: str = os.getenv("DEMO_MANAGER_PASSWORD", "")


@lru_cache
def get_settings() -> Settings:
    return Settings()
