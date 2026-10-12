"""Settings. Everything is read from the environment, prefixed DREAMLOG_."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DREAMLOG_", env_file=str(REPO_ROOT / ".env"), extra="ignore")

    database_url: str = "postgresql://dreamlog:dreamlog@localhost:5504/dreamlog"
    data_dir: Path = REPO_ROOT / "data"
    """Root of the local object store (audio, illustrations, atlases) and the dev key."""
    model_cache_dir: Path = REPO_ROOT / ".cache" / "models"

    encryption_key: str = ""
    """Base64 of 32 random bytes. Empty means: generate one into data_dir on first run."""
    keep_audio: bool = False
    """Audio is deleted as soon as it has been transcribed unless this is true."""

    transcriber: Literal["faster-whisper", "fake"] = "faster-whisper"
    whisper_model: str = "base.en"
    whisper_compute_type: str = "int8"

    embedder: Literal["fastembed", "hash"] = "fastembed"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    canonical_threshold: float = 0.60
    """Cosine similarity at or above which a new symbol joins an existing one."""

    extractor: Literal["auto", "lexicon", "anthropic"] = "auto"
    """auto uses the LLM when ANTHROPIC_API_KEY is set and the lexicon otherwise."""
    llm_model: str = "claude-sonnet-5-5"
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")

    illustrator: Literal["auto", "procedural", "api"] = "auto"
    """auto uses the image API when DREAMLOG_IMAGE_API_KEY is set and the built-in painter otherwise."""
    image_api_url: str = "https://api.openai.com/v1/images/generations"
    image_api_key: str = ""
    image_model: str = "gpt-image-1"

    search_limit: int = 10
    search_floor: float = 0.2
    """Semantic matches below this cosine similarity are not shown."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
