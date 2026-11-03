"""Settings, read from environment variables (prefix TERRAIN_) or a .env file."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TERRAIN_", env_file=".env", extra="ignore")

    app_name: str = "Terrain Studio API"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"
    storage_dir: Path = Path("storage")
    cors_origins: list[str] = ["*"]
    max_png_pixels: int = 4_000_000      # map images are down-sampled above this
    max_histogram_bins: int = 1000

    @property
    def projects_dir(self) -> Path:
        return self.storage_dir / "projects"

    @property
    def exports_dir(self) -> Path:
        return self.storage_dir / "exports"

    def ensure_dirs(self) -> None:
        for d in (self.projects_dir, self.exports_dir, self.storage_dir / "cache",
                  self.storage_dir / "temp"):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
