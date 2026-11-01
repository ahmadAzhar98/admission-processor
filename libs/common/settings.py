"""Runtime settings read from environment variables and OpenFaaS secrets.

Variables use the ``AP_`` prefix (for example ``AP_S3_BUCKET``). Secret
fields are also read from files in the OpenFaaS secrets directory, named
after the field with hyphens because Kubernetes secret names cannot hold
underscores (for example ``/var/openfaas/secrets/database-url``). An
environment variable, when set, takes precedence over the secret file.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

OPENFAAS_SECRETS_DIR = Path("/var/openfaas/secrets")
SECRET_FIELDS = ("database_url", "s3_access_key", "s3_secret_key")


class Settings(BaseSettings):
    """All configuration a function may need; every field has a dev default."""

    model_config = SettingsConfigDict(env_prefix="AP_", extra="ignore", frozen=True)

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    tenants_dir: Path = Path("tenants")

    database_url: SecretStr = SecretStr("postgresql://admission:admission@localhost:5432/admission")
    redis_url: str = "redis://localhost:6379/0"

    s3_endpoint: str = "http://localhost:8333"
    s3_region: str = "us-east-1"
    s3_bucket: str = "admission-documents"
    s3_access_key: SecretStr = SecretStr("admission")
    s3_secret_key: SecretStr = SecretStr("admission-secret")

    gateway_url: str = "http://127.0.0.1:8080"
    ollama_url: str = "http://localhost:11434"
    llm_model: str = "qwen2.5:7b-instruct"
    embedding_model: str = "nomic-embed-text"
    http_timeout_seconds: float = Field(default=30.0, gt=0)
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)


def read_secret_files(secrets_dir: Path) -> dict[str, Any]:
    """Read secret fields from ``secrets_dir`` unless overridden by env vars.

    Args:
        secrets_dir: Directory holding one file per secret.

    Returns:
        Mapping of field name to secret value for each file found.
    """
    values: dict[str, Any] = {}
    for field in SECRET_FIELDS:
        path = secrets_dir / field.replace("_", "-")
        if path.is_file() and f"AP_{field.upper()}" not in os.environ:
            values[field] = path.read_text(encoding="utf-8").strip()
    return values


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return process-wide settings, read once and cached.

    The OpenFaaS secrets directory is only consulted when it exists, so the
    same code runs unchanged in tests and local development.
    """
    if OPENFAAS_SECRETS_DIR.is_dir():
        return Settings(**read_secret_files(OPENFAAS_SECRETS_DIR))
    return Settings()
