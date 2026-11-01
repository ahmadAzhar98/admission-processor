from pathlib import Path

from common.ocr import StaticOcrEngine
from common.runtime import in_memory_runtime
from common.schemas.events import PipelineStep

from functions.local_runner import LocalPipeline

TENANTS = Path(__file__).resolve().parents[2] / "tenants"


def test_upload_and_drain_follow_the_queue():
    rt = in_memory_runtime(TENANTS)
    rt.ocr = StaticOcrEngine("unused")
    pipeline = LocalPipeline(rt)
    result = pipeline.upload("uni-c", "app-1", b"not an image")
    assert not result.duplicate
    assert pipeline.drain() == 2  # quality-check rejects, notify sends
    steps = [event.step for event, _ in pipeline.trace]
    assert steps == [PipelineStep.QUALITY_CHECK, PipelineStep.NOTIFY]
    assert pipeline.channel.sent[0].event == "reupload_required"
