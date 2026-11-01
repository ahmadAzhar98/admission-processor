"""Guard the GitHub Actions workflows against unsafe or broken changes."""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parents[3] / ".github" / "workflows"


def _load(name: str) -> dict[str, Any]:
    raw: dict[Any, Any] = yaml.safe_load((WORKFLOWS / name).read_text())
    # PyYAML reads the bare key `on` as boolean True.
    return {("on" if key is True else str(key)): value for key, value in raw.items()}


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job["steps"]]


@pytest.fixture(params=sorted(p.name for p in WORKFLOWS.glob("*.yml")))
def workflow(request):
    return _load(request.param)


def test_ci_checks_every_push_to_main_and_pull_request():
    ci = _load("ci.yml")
    assert ci["on"]["push"]["branches"] == ["main"]
    assert "pull_request" in ci["on"]
    assert any(step.get("run") == "make check" for step in _steps(ci))


def test_release_runs_only_for_version_tags():
    release = _load("release.yml")
    assert release["on"] == {"push": {"tags": ["v*.*.*"]}}


def test_release_permissions_are_least_privilege():
    release = _load("release.yml")
    jobs = release["jobs"]
    assert release["permissions"] == {"contents": "read"}
    assert jobs["images"]["permissions"] == {"contents": "read", "packages": "write"}
    assert jobs["release"]["permissions"] == {"contents": "write"}
    assert "permissions" not in jobs["verify"]


def test_nothing_is_published_before_verification():
    jobs = _load("release.yml")["jobs"]
    assert jobs["images"]["needs"] == "verify"
    assert set(jobs["release"]["needs"]) == {"verify", "images"}
    runs = [step.get("run", "") for step in jobs["verify"]["steps"]]
    assert any("check-version" in r for r in runs)
    assert "make check" in runs


def test_images_cover_the_stack_functions():
    images = _load("release.yml")["jobs"]["images"]
    assert (
        images["strategy"]["matrix"]["function"] == "${{ fromJSON(needs.verify.outputs.matrix) }}"
    )
    publish = next(s for s in images["steps"] if "faas-cli publish" in s.get("run", ""))
    assert publish["env"]["TAG"] == "${{ needs.verify.outputs.version }}"


def test_workflows_never_push_to_the_repository(workflow):
    for step in _steps(workflow):
        assert not re.search(r"\bgit\s+push\b", step.get("run", "")), step


def test_actions_and_tools_are_pinned(workflow):
    for step in _steps(workflow):
        if "uses" in step:
            assert re.search(r"@v\d+", step["uses"]), step["uses"]
    env = workflow.get("env", {})
    if "FAAS_CLI_VERSION" in env:
        assert re.fullmatch(r"\d+\.\d+\.\d+", env["FAAS_CLI_VERSION"])
