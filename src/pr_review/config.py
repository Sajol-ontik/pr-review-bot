from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_app_id: int = 0
    github_app_private_key_path: str = ""
    github_webhook_secret: str = ""

    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"

    dashboard_username: str = "admin"
    dashboard_password: str = "admin"

    public_base_url: str = "http://localhost:8000"
    pass_threshold: int = 70
    max_diff_chars: int = 60000
    database_url: str = "sqlite:///./pr_review.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("github_app_id", mode="before")
    @classmethod
    def _coerce_int(cls, v: object) -> int:
        if v in ("", None):
            return 0
        return int(v)

    @property
    def private_key(self) -> str:
        path = Path(self.github_app_private_key_path)
        if not path.exists():
            return ""
        return path.read_text()


settings = Settings()