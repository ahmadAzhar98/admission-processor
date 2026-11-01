from common.errors import UpstreamServiceError
from common.llm import FakeLlmClient

from functions.classify.llm_fallback import MAX_TEXT_CHARS, build_prompt, classify_with_llm


def test_prompt_lists_types_and_truncates_text():
    prompt = build_prompt("x" * (MAX_TEXT_CHARS + 500))
    assert "fsc_result" in prompt and "unknown" in prompt
    assert "x" * MAX_TEXT_CHARS in prompt
    assert "x" * (MAX_TEXT_CHARS + 1) not in prompt


def test_valid_answer_becomes_result():
    llm = FakeLlmClient(lambda p: {"document_type": "domicile", "confidence": 0.82})
    result = classify_with_llm(llm, "garbled text")
    assert result is not None
    assert result.document_type == "domicile"
    assert result.method == "llm"


def test_invalid_answer_returns_none():
    llm = FakeLlmClient(lambda p: {"document_type": "passport", "confidence": 2})
    assert classify_with_llm(llm, "text") is None


def test_llm_outage_returns_none():
    def boom(prompt):
        raise UpstreamServiceError("down")

    assert classify_with_llm(FakeLlmClient(boom), "text") is None
