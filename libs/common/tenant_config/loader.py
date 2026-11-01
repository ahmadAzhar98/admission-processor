"""Load tenant configs from YAML/JSON files and look them up by tenant ID."""

import json
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from common.errors import TenantConfigError, TenantNotFoundError
from common.tenant import validate_tenant_id
from common.tenant_config.models import ConfigStatus, TenantConfig

logger = logging.getLogger(__name__)

SUFFIXES = (".yaml", ".yml", ".json")


def parse_config(data: Any, source: str = "<memory>") -> TenantConfig:
    """Validate already-parsed config data.

    Raises:
        TenantConfigError: With every validation problem listed, if invalid.
    """
    try:
        return TenantConfig.model_validate(data)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        )
        raise TenantConfigError(f"{source}: {problems}") from exc


def load_config_file(path: Path) -> TenantConfig:
    """Read and validate one tenant config file.

    The file name (without suffix) must equal the ``tenant_id`` inside, so a
    copied file cannot silently serve under the wrong tenant.

    Raises:
        TenantConfigError: If the file cannot be read, parsed or validated.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise TenantConfigError(f"{path}: cannot read config") from exc
    config = parse_config(data, str(path))
    if config.tenant_id != path.stem:
        raise TenantConfigError(f"{path}: tenant_id {config.tenant_id!r} does not match file name")
    return config


class TenantRegistry:
    """Caches tenant configs read from a directory, one file per tenant."""

    def __init__(self, directory: Path) -> None:
        """Serve configs from ``directory``; files are read on first use."""
        self.directory = directory
        self._cache: dict[str, TenantConfig] = {}

    def _path_for(self, tenant_id: str) -> Path | None:
        for suffix in SUFFIXES:
            path = self.directory / f"{tenant_id}{suffix}"
            if path.is_file():
                return path
        return None

    def get(self, tenant_id: str, *, allow_pending: bool = False) -> TenantConfig:
        """Return the config for ``tenant_id``.

        Args:
            tenant_id: Tenant slug.
            allow_pending: Return configs still awaiting admin approval. The
                pipeline leaves this off so drafts never process documents.

        Raises:
            TenantNotFoundError: If no config file exists, or it is pending
                and ``allow_pending`` is false.
            TenantConfigError: If the file is invalid.
        """
        validate_tenant_id(tenant_id)
        config = self._cache.get(tenant_id)
        if config is None:
            path = self._path_for(tenant_id)
            if path is None:
                raise TenantNotFoundError(tenant_id)
            config = load_config_file(path)
            self._cache[tenant_id] = config
            logger.info("tenant config loaded", extra={"config_tenant": tenant_id})
        if config.status is ConfigStatus.PENDING_APPROVAL and not allow_pending:
            raise TenantNotFoundError(f"{tenant_id} is pending approval")
        return config

    def tenant_ids(self) -> list[str]:
        """Return IDs of all config files in the directory, sorted."""
        return sorted(
            p.stem for p in self.directory.iterdir() if p.is_file() and p.suffix in SUFFIXES
        )

    def clear(self) -> None:
        """Drop cached configs so the next lookup re-reads files."""
        self._cache.clear()
