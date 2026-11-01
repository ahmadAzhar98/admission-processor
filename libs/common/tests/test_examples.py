from common.llm import FakeLlmClient
from common.repositories.examples import (
    FewShotExample,
    InMemoryExampleRepository,
    cosine,
    vector_literal,
)
from common.schemas.documents import DocumentType

LLM = FakeLlmClient(dimensions=128)


def _example(tenant_id, source, text, document_type=DocumentType.FSC_RESULT):
    return FewShotExample(
        tenant_id=tenant_id,
        document_type=document_type,
        source_document_id=source,
        ocr_text=text,
        fields={"board": text.split()[-1]},
    )


def _add(repo, example):
    repo.add(example, LLM.embed(example.ocr_text))


def test_nearest_is_tenant_and_type_scoped():
    repo = InMemoryExampleRepository()
    _add(repo, _example("uni-a", "d1", "Board BISE Lahore"))
    _add(repo, _example("uni-b", "d2", "Board BISE Lahore"))
    _add(repo, _example("uni-a", "d3", "Board BISE Lahore", DocumentType.MATRIC_RESULT))
    found = repo.nearest("uni-a", DocumentType.FSC_RESULT, LLM.embed("Board BISE Lahore"), 5)
    assert [e.source_document_id for e in found] == ["d1"]


def test_most_similar_first_and_k_limits():
    repo = InMemoryExampleRepository()
    _add(repo, _example("uni-a", "far", "Fee challan bank amount paid"))
    _add(repo, _example("uni-a", "near", "Higher Secondary Certificate BISE Multan"))
    query = LLM.embed("Higher Secondary Certificate BISE Lahore")
    found = repo.nearest("uni-a", DocumentType.FSC_RESULT, query, 1)
    assert [e.source_document_id for e in found] == ["near"]


def test_re_adding_same_source_replaces():
    repo = InMemoryExampleRepository()
    _add(repo, _example("uni-a", "d1", "old text Lahore"))
    _add(repo, _example("uni-a", "d1", "new text Multan"))
    assert len(repo.items) == 1


def test_helpers():
    assert cosine([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
    assert vector_literal([0.5, 1.0]) == "[0.500000,1.000000]"
