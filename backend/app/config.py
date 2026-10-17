from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FORTE_", env_file=BACKEND_DIR / ".env", extra="ignore"
    )

    api_key: SecretStr
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    data_dir: Path = BACKEND_DIR / "data"
    max_upload_mb: int = Field(default=250, ge=1, le=2048)
    max_pending_jobs: int = Field(default=4, ge=1, le=100)
    job_timeout_seconds: int = Field(default=270, ge=1, le=290)
    retention_hours: int = Field(default=24, ge=1, le=168)
    ffprobe: str = "ffprobe"

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value: SecretStr) -> SecretStr:
        key = value.get_secret_value()
        if len(key) < 24 or key == "replace-with-a-random-key":
            raise ValueError("Generate FORTE_API_KEY with secrets.token_urlsafe(32)")
        return value

    @field_validator("data_dir")
    @classmethod
    def absolute_data_dir(cls, value: Path) -> Path:
        return (BACKEND_DIR / value).resolve() if not value.is_absolute() else value.resolve()

    @property
    def database(self) -> Path:
        return self.data_dir / "jobs.sqlite3"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024
