import copy
import json

import pytest
import yaml

from common.errors import TenantConfigError, TenantError, TenantNotFoundError
from common.tenant_config.loader import TenantRegistry, load_config_file, parse_config
from common.tests.test_tenant_config_models import BASE


def _write(tmp_path, name, data, fmt="yaml"):
    path = tmp_path / f"{name}.{fmt}"
    text = yaml.safe_dump(data, allow_unicode=True) if fmt == "yaml" else json.dumps(data)
    path.write_text(text, encoding="utf-8")
    return path


def test_load_yaml_and_json(tmp_path):
    assert load_config_file(_write(tmp_path, "uni-x", BASE)).tenant_id == "uni-x"
    other = tmp_path / "json"
    other.mkdir()
    assert load_config_file(_write(other, "uni-x", BASE, "json")).display_name == "University X"


def test_file_name_must_match_tenant_id(tmp_path):
    with pytest.raises(TenantConfigError, match="does not match"):
        load_config_file(_write(tmp_path, "uni-y", BASE))


def test_errors_list_every_problem():
    data = copy.deepcopy(BASE)
    data["admission_cycle"] = "next year"
    data["retention_days"] = 0
    with pytest.raises(TenantConfigError) as info:
        parse_config(data, "x.yaml")
    assert "admission_cycle" in str(info.value)
    assert "retention_days" in str(info.value)


def test_malformed_yaml_is_a_config_error(tmp_path):
    path = tmp_path / "uni-x.yaml"
    path.write_text("documents: [unclosed", encoding="utf-8")
    with pytest.raises(TenantConfigError):
        load_config_file(path)


def test_registry_caches_and_lists(tmp_path):
    _write(tmp_path, "uni-x", BASE)
    registry = TenantRegistry(tmp_path)
    first = registry.get("uni-x")
    assert registry.get("uni-x") is first
    assert registry.tenant_ids() == ["uni-x"]
    with pytest.raises(TenantNotFoundError):
        registry.get("uni-z")
    with pytest.raises(TenantError):
        registry.get("../uni-x")


def test_pending_configs_are_hidden_from_the_pipeline(tmp_path):
    _write(tmp_path, "uni-x", {**BASE, "status": "pending_approval"})
    registry = TenantRegistry(tmp_path)
    with pytest.raises(TenantNotFoundError):
        registry.get("uni-x")
    assert registry.get("uni-x", allow_pending=True).status == "pending_approval"
