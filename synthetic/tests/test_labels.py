from synthetic.labels import GroundTruth, InjectedMismatch, read_manifest, write_manifest


def _label(i):
    return GroundTruth(
        tenant_id="uni-a",
        application_id=f"app-{i}",
        document_id=f"doc-{i}",
        document_type="cnic",
        language="en",
        layout="card",
        fields={"full_name": "Ali Khan", "obtained_marks": 900},
        text="Name: Ali Khan",
        profile="clean",
        injected_mismatch=InjectedMismatch(
            document_type="cnic", field="full_name", original="Ali Khan", altered="Ali Kahn"
        )
        if i == 1
        else None,
    )


def test_manifest_roundtrip(tmp_path):
    labels = [_label(0), _label(1)]
    path = write_manifest(labels, tmp_path)
    assert read_manifest(path) == labels
    assert read_manifest(tmp_path) == labels
