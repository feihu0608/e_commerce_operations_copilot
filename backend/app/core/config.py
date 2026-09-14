from functools import lru_cache
from pydantic import BaseModel, model_validator
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
    app_version: str = os.getenv("APP_VERSION", "dev")
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    task_lease_seconds: int = int(os.getenv("TASK_LEASE_SECONDS", "120"))
    outbox_poll_seconds: float = float(os.getenv("OUTBOX_POLL_SECONDS", "2"))
    media_max_bytes: int = int(os.getenv("MEDIA_MAX_BYTES", str(50 * 1024 * 1024)))
    video_poll_seconds: int = int(os.getenv("VIDEO_POLL_SECONDS", "5"))
    video_max_polls: int = int(os.getenv("VIDEO_MAX_POLLS", "84"))
    langgraph_checkpoint_mode: str = os.getenv("LANGGRAPH_CHECKPOINT_MODE", "postgres")
    demo_operator_password: str = os.getenv("DEMO_OPERATOR_PASSWORD", "")
    demo_manager_password: str = os.getenv("DEMO_MANAGER_PASSWORD", "")

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @model_validator(mode="after")
    def validate_deployment_secrets(self):
        if self.app_env == "production" and self.app_secret_key == "dev-only-change-me":
            raise ValueError("APP_SECRET_KEY must be changed in production")
        if self.ai_mode not in {"mock", "live"} or self.media_mode not in {"mock", "live"}:
            raise ValueError("AI_MODE and MEDIA_MODE must be mock or live")
        if self.langgraph_checkpoint_mode not in {"postgres", "memory"}:
            raise ValueError("LANGGRAPH_CHECKPOINT_MODE must be postgres or memory")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
