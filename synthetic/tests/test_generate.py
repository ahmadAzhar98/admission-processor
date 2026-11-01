import random
from pathlib import Path

import pytest
from common.tenant_config.loader import TenantRegistry

from synthetic.generate import generate, generate_application, perturb_name
from synthetic.labels import read_manifest

REGISTRY = TenantRegistry(Path(__file__).resolve().parents[2] / "tenants")


def test_labels_only_generation_is_reproducible():
    a = generate(REGISTRY, ["uni-a", "uni-b"], 5, seed=1, out_dir=None)
    b = generate(REGISTRY, ["uni-a", "uni-b"], 5, seed=1, out_dir=None)
    assert a == b
    assert {label.tenant_id for label in a} == {"uni-a", "uni-b"}


def test_tenant_requirements_drive_document_set():
    config_b = REGISTRY.get("uni-b")
    config_c = REGISTRY.get("uni-c")
    types_b = {lbl.document_type for lbl in generate_application(config_b, 0, 3, None)}
    types_c = {lbl.document_type for lbl in generate_application(config_c, 0, 3, None)}
    assert "domicile" in types_b
    assert "domicile" not in types_c and "entry_test" not in types_c


def test_adding_applications_does_not_change_earlier_ones():
    small = generate(REGISTRY, ["uni-c"], 2, seed=9, out_dir=None)
    large = generate(REGISTRY, ["uni-c"], 4, seed=9, out_dir=None)
    assert large[: len(small)] == small


def test_mismatches_are_planted_and_labelled():
    labels = generate(REGISTRY, ["uni-a"], 60, seed=2, out_dir=None)
    planted = [lbl for lbl in labels if lbl.injected_mismatch]
    assert planted
    for lbl in planted:
        mismatch = lbl.injected_mismatch
        assert mismatch is not None
        assert lbl.fields["full_name"] == mismatch.altered
        assert mismatch.altered in lbl.text


@pytest.mark.parametrize("seed", range(20))
def test_perturb_name_changes_the_name(seed):
    assert perturb_name("Ayesha Khan", random.Random(seed)) != "Ayesha Khan"


def test_images_and_manifest_are_written(tmp_path):
    labels = generate(REGISTRY, ["uni-c"], 1, seed=4, out_dir=tmp_path)
    assert read_manifest(tmp_path) == labels
    for label in labels:
        assert label.image_path is not None
        assert (tmp_path / label.image_path).is_file()
        assert (tmp_path / label.image_path).with_suffix(".json").is_file()


def test_labels_match_with_and_without_images(tmp_path):
    without = generate(REGISTRY, ["uni-c"], 1, seed=6, out_dir=None)
    with_images = generate(REGISTRY, ["uni-c"], 1, seed=6, out_dir=tmp_path)
    assert [lbl.fields for lbl in without] == [lbl.fields for lbl in with_images]
    assert [lbl.profile for lbl in without] == [lbl.profile for lbl in with_images]
