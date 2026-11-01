from pathlib import Path

import pytest

from common import runtime as runtime_module
from common.runtime import get_runtime, in_memory_runtime, set_runtime
from common.settings import Settings

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture(autouse=True)
def _reset():
    yield
    set_runtime(None)


def test_in_memory_runtime_is_usable():
    rt = in_memory_runtime(TENANTS)
    set_runtime(rt)
    assert get_runtime() is rt
    assert rt.tenants.get("uni-a").display_name == "University A"
    key = rt.tenant_storage("uni-a").put(("x",), b"1", "text/plain")
    assert key == "tenants/uni-a/x"


def test_get_runtime_builds_once(monkeypatch):
    built = []

    def fake_build(settings):
        built.append(settings)
        return in_memory_runtime(TENANTS, settings)

    monkeypatch.setattr(runtime_module, "build_runtime", fake_build)
    first = get_runtime()
    assert get_runtime() is first
    assert len(built) == 1


def test_build_runtime_does_not_connect_eagerly():
    rt = runtime_module.build_runtime(Settings(tenants_dir=TENANTS))
    assert rt.database is not None
    rt.database.close()
