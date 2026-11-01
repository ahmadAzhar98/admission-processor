import pytest

from common import settings as settings_module
from common.settings import Settings, get_settings, read_secret_files


def test_defaults_are_usable_without_environment():
    s = Settings()
    assert s.environment == "dev"
    assert s.s3_bucket == "admission-documents"


def test_environment_overrides_use_prefix(monkeypatch):
    monkeypatch.setenv("AP_S3_BUCKET", "other-bucket")
    monkeypatch.setenv("AP_ENVIRONMENT", "test")
    s = Settings()
    assert s.s3_bucket == "other-bucket"
    assert s.environment == "test"


def test_secrets_are_not_exposed_in_repr(monkeypatch):
    monkeypatch.setenv("AP_DATABASE_URL", "postgresql://u:supersecret@db/x")
    s = Settings()
    assert "supersecret" not in repr(s)
    assert s.database_url.get_secret_value().endswith("@db/x")


def test_secrets_dir_is_read_when_present(monkeypatch, tmp_path):
    (tmp_path / "s3-secret-key").write_text("from-file")
    monkeypatch.setattr(settings_module, "OPENFAAS_SECRETS_DIR", tmp_path)
    get_settings.cache_clear()
    try:
        assert get_settings().s3_secret_key.get_secret_value() == "from-file"
    finally:
        get_settings.cache_clear()


def test_environment_variable_beats_secret_file(monkeypatch, tmp_path):
    (tmp_path / "s3-secret-key").write_text("from-file")
    monkeypatch.setenv("AP_S3_SECRET_KEY", "from-env")
    assert read_secret_files(tmp_path) == {}


def test_invalid_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("AP_ENVIRONMENT", "staging")
    with pytest.raises(ValueError):
        Settings()
