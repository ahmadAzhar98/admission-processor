from common.schemas.events import PipelineEvent, PipelineStep


def _event():
    return PipelineEvent(
        tenant_id="uni-b", application_id="app-1", document_id="doc-1", step="classify"
    )


def test_step_values_are_function_names():
    assert PipelineStep.QUALITY_CHECK.value == "quality-check"


def test_idempotency_key_is_stable_across_redelivery():
    event = _event()
    clone = PipelineEvent.model_validate_json(event.model_dump_json())
    assert clone.idempotency_key == event.idempotency_key == "uni-b:doc-1:classify"


def test_next_keeps_identity_and_correlation():
    event = _event()
    nxt = event.next(PipelineStep.EXTRACT, {"document_type": "cnic"})
    assert nxt.step is PipelineStep.EXTRACT
    assert nxt.correlation_id == event.correlation_id
    assert nxt.document_id == event.document_id
    assert nxt.payload == {"document_type": "cnic"}
    assert event.step is PipelineStep.CLASSIFY
