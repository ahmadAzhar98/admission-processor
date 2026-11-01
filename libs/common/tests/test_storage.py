import pytest

from common.errors import ObjectNotFoundError, StorageError, TenantError
from common.storage import InMemoryObjectStore, TenantStorage, tenant_key


def test_tenant_key_layout():
    assert tenant_key("uni-a", "applications", "app-1", "doc.png") == (
        "tenants/uni-a/applications/app-1/doc.png"
    )


@pytest.mark.parametrize("part", ["..", "", "a/b", ".hidden"])
def test_tenant_key_rejects_unsafe_parts(part):
    with pytest.raises(StorageError):
        tenant_key("uni-a", part)


def test_tenant_key_rejects_bad_tenant():
    with pytest.raises(TenantError):
        tenant_key("../uni-a", "x")


def test_in_memory_store_roundtrip():
    store = InMemoryObjectStore()
    store.put("k/1", b"data", "text/plain")
    assert store.exists("k/1")
    assert store.get("k/1") == b"data"
    assert store.list("k/") == ["k/1"]
    store.delete("k/1")
    store.delete("k/1")
    with pytest.raises(ObjectNotFoundError):
        store.get("k/1")


def test_tenants_cannot_see_each_other():
    store = InMemoryObjectStore()
    a = TenantStorage(store, "uni-a")
    b = TenantStorage(store, "uni-b")
    key = a.put(("applications", "app-1", "doc.png"), b"img", "image/png")
    assert key.startswith("tenants/uni-a/")
    assert a.get("applications", "app-1", "doc.png") == b"img"
    assert not b.exists("applications", "app-1", "doc.png")
    assert b.list() == []
    with pytest.raises(StorageError):
        b.get_key(key)
    assert a.get_key(key) == b"img"
