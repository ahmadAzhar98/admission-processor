"""End-to-end run of every step over rendered synthetic applications.

Images go through the real quality check; OCR returns each document's
ground-truth text so the rest of the pipeline is tested without OCR
models. No network, database or LLM is used.
"""

import hashlib
from collections import defaultdict
from pathlib import Path

import pytest
from common.llm import FakeLlmClient
from common.ocr.label import LabelOcrEngine
from common.runtime import in_memory_runtime
from common.schemas.events import PipelineStep
from common.tenant_config.loader import TenantRegistry

from functions.local_runner import LocalPipeline
from synthetic.generate import generate

TENANTS = Path(__file__).resolve().parents[2] / "tenants"
OUTCOMES = {"approved", "needs_review", "rejected", "incomplete"}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("dataset")
    labels = generate(TenantRegistry(TENANTS), ["uni-a", "uni-b", "uni-c"], 3, seed=5, out_dir=out)
    rt = in_memory_runtime(TENANTS)
    ocr = LabelOcrEngine()
    rt.ocr, rt.llm = ocr, FakeLlmClient()
    pipeline = LocalPipeline(rt)
    uploads = []
    for label in labels:
        assert label.image_path is not None
        data = (out / label.image_path).read_bytes()
        ocr.register(data, label.text)
        uploads.append((label, data))
        pipeline.upload(label.tenant_id, label.application_id, data)
    pipeline.drain()
    return rt, pipeline, labels, uploads


def _applications(labels):
    apps = defaultdict(list)
    for label in labels:
        apps[(label.tenant_id, label.application_id)].append(label)
    return apps


def _last_decision(pipeline, tenant_id, application_id):
    decisions = [
        summary["outcome"]
        for event, summary in pipeline.trace
        if event.step is PipelineStep.DECIDE
        and (event.tenant_id, event.application_id) == (tenant_id, application_id)
        and summary["outcome"] != "waiting"
    ]
    return decisions[-1] if decisions else None


def test_every_application_reaches_an_outcome(run):
    rt, pipeline, labels, _ = run
    for tenant_id, application_id in _applications(labels):
        outcome = _last_decision(pipeline, tenant_id, application_id)
        reupload = any(
            rt.documents.get(tenant_id, d.document.document_id).status == "reupload_required"
            for d in rt.documents.list_for_application(tenant_id, application_id)
        )
        assert outcome in OUTCOMES or reupload, (tenant_id, application_id)


def test_planted_name_mismatches_are_never_auto_approved(run):
    _, pipeline, labels, _ = run
    for (tenant_id, application_id), docs in _applications(labels).items():
        if any(d.injected_mismatch for d in docs):
            assert _last_decision(pipeline, tenant_id, application_id) != "approved"


def test_documents_are_classified_as_labelled(run):
    rt, _, _, uploads = run
    expected = {hashlib.sha256(data).hexdigest(): label.document_type for label, data in uploads}
    classified = [r for r in rt.documents.records.values() if r.document_type is not None]
    assert classified
    for record in classified:
        assert record.document_type == expected[record.document.sha256]


def test_reupload_of_everything_is_a_no_op(run):
    rt, pipeline, _, uploads = run
    results_before = len(rt.results.results)
    reviews_before = len(rt.reviews.items)
    for label, data in uploads:
        assert pipeline.upload(label.tenant_id, label.application_id, data).duplicate
    assert pipeline.drain() == 0
    assert len(rt.results.results) == results_before
    assert len(rt.reviews.items) == reviews_before


def test_replayed_decisions_do_not_duplicate_effects(run):
    rt, pipeline, _, _ = run
    decide_events = [e for e, _ in pipeline.trace if e.step is PipelineStep.DECIDE]
    reviews_before, sent_before = len(rt.reviews.items), len(pipeline.channel.sent)
    rt.publisher.events.extend(decide_events)
    pipeline.drain()
    assert len(rt.reviews.items) == reviews_before
    assert len(pipeline.channel.sent) == sent_before
