from pathlib import Path

import pytest

from infra.ci import release_tools
from infra.ci.release_tools import (
    ReleaseError,
    check_version,
    function_matrix,
    image_registry,
    release_notes,
    version_from_tag,
)

ROOT = Path(__file__).resolve().parents[3]

CHANGELOG = """## v1.1.0 (2026-11-02)

### CI

- publish images on tags

## v1.0.0 (2026-11-01)

### Documentation

- add deployment guide
"""


@pytest.mark.parametrize("tag", ["1.0.0", "v1.0", "v1.0.0-rc1", "release-1"])
def test_malformed_tags_are_rejected(tag):
    with pytest.raises(ReleaseError):
        version_from_tag(tag)


def test_tag_must_match_pyproject(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "1.1.0"\n')
    assert check_version("v1.1.0", pyproject) == "1.1.0"
    with pytest.raises(ReleaseError, match="does not match"):
        check_version("v1.2.0", pyproject)


def test_repository_version_matches_latest_tag_format():
    version = check_version("v" + _project_version(), ROOT / "pyproject.toml")
    assert version.count(".") == 2


def _project_version() -> str:
    import tomllib

    return str(tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"])


def test_matrix_lists_every_stack_function():
    matrix = function_matrix(ROOT / "stack.yml")
    names = [entry["name"] for entry in matrix]
    assert names == sorted(names)
    assert {"intake", "quality-check", "classify", "decide", "review-api"} <= set(names)
    assert all(Path(ROOT, entry["handler"]).is_dir() for entry in matrix)
    assert {entry["lang"] for entry in matrix} <= {"python3-http", "dockerfile"}


def test_registry_is_lowercase():
    assert image_registry("ahmadAzhar98") == "ghcr.io/ahmadazhar98"


def test_release_notes_extracts_one_section():
    notes = release_notes(CHANGELOG, "v1.1.0")
    assert "publish images on tags" in notes
    assert "add deployment guide" not in notes
    assert release_notes(CHANGELOG, "v1.0.0").startswith("### Documentation")
    with pytest.raises(ReleaseError):
        release_notes(CHANGELOG, "v0.9.0")


def test_release_notes_for_shipped_changelog():
    changelog = (ROOT / "CHANGELOG.md").read_text()
    assert release_notes(changelog, "v1.0.0").strip()


def test_cli(capsys):
    assert release_tools.main(["registry", "Org"]) == 0
    assert capsys.readouterr().out == "ghcr.io/org\n"
    assert release_tools.main(["check-version", "nope"]) == 1
    assert release_tools.main([]) == 2
