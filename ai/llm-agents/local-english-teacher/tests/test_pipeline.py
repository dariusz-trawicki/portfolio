"""End-to-end pipeline tests with fake STT / LLM / TTS (no models needed)."""

import numpy as np
import pytest

from english_teacher.config import TeacherConfig
from english_teacher.llm import LLMResult, parse_response
from english_teacher.memory import ConversationHistory, MistakeStore
from english_teacher.metrics import Metrics
from english_teacher.pipeline import FALLBACK_REPLY, TeacherPipeline


class FakeSTT:
    def __init__(self, text="Yesterday I goed to the office."):
        self.text = text

    def transcribe(self, sample_rate, audio):
        return self.text


class FakeLLM:
    def __init__(self, reply=None, fail=False):
        self.reply = reply or (
            'Good. Small correction: you said "I goed", better is "I went". What did you do there?'
        )
        self.fail = fail
        self.calls = []

    def chat(self, messages):
        self.calls.append(messages)
        if self.fail:
            raise ConnectionError("ollama down")
        return LLMResult(self.reply, prompt_tokens=120, completion_tokens=30, eval_seconds=1.5)


class FakeTTS:
    name = "fake"

    def __init__(self):
        self.texts = []

    def synthesize(self, text):
        self.texts.append(text)
        return 16000, np.ones(16000, dtype=np.int16)  # 1 second


def value(metrics, name, labels=None):
    return metrics.registry.get_sample_value(name, labels or {}) or 0.0


@pytest.fixture
def make_pipeline(tmp_path):
    def _make(stt=None, llm=None, tts=None, max_history=16, context_window=0):
        return TeacherPipeline(
            cfg=TeacherConfig(level="B2", topic="MLOps interview"),
            stt=stt or FakeSTT(),
            llm=llm or FakeLLM(),
            tts=tts or FakeTTS(),
            history=ConversationHistory(max_history),
            mistakes=MistakeStore(tmp_path / "mistakes.json"),
            metrics=Metrics(),
            chunk_seconds=0.5,
            context_window=context_window,
        )

    return _make


AUDIO = (48000, np.zeros((1, 48000), dtype=np.int16))


def test_full_turn(make_pipeline):
    tts = FakeTTS()
    p = make_pipeline(tts=tts)
    chunks = list(p.handle(AUDIO))

    assert len(chunks) == 2  # 1 s of audio in 0.5 s chunks
    assert tts.texts[0].startswith("Good.")
    assert p.mistakes.load()[0]["wrong"] == "I goed"
    assert len(p.history) == 2

    m = p.metrics
    assert value(m, "teacher_turns_total") == 1
    assert value(m, "teacher_corrections_total") == 1
    assert value(m, "teacher_llm_tokens_total", {"type": "prompt"}) == 120
    assert value(m, "teacher_response_latency_seconds_count") == 1
    for stage in ("stt", "llm", "tts"):
        assert value(m, "teacher_stage_latency_seconds_count", {"stage": stage}) == 1


def test_history_and_mistakes_reach_the_prompt(make_pipeline):
    llm = FakeLLM()
    p = make_pipeline(llm=llm)
    list(p.handle(AUDIO))
    list(p.handle(AUDIO))

    second = llm.calls[1]
    assert second[0]["role"] == "system"
    assert "B2" in second[0]["content"]
    assert "MLOps interview" in second[0]["content"]
    assert '"I goed" -> "I went"' in second[0]["content"]
    assert [m["role"] for m in second[1:]] == ["user", "assistant", "user"]


def test_empty_transcript_is_skipped(make_pipeline):
    tts = FakeTTS()
    p = make_pipeline(stt=FakeSTT(""), tts=tts)
    assert list(p.handle(AUDIO)) == []
    assert tts.texts == []
    assert value(p.metrics, "teacher_empty_transcripts_total") == 1


def test_llm_failure_speaks_fallback_and_is_not_remembered(make_pipeline):
    tts = FakeTTS()
    p = make_pipeline(llm=FakeLLM(fail=True), tts=tts)
    chunks = list(p.handle(AUDIO))

    assert chunks
    assert tts.texts == [FALLBACK_REPLY]
    assert len(p.history) == 0
    assert value(p.metrics, "teacher_errors_total", {"stage": "llm"}) == 1


def test_memory_saved_even_if_playback_is_stopped(make_pipeline):
    p = make_pipeline()
    gen = p.handle(AUDIO)
    next(gen)  # user presses Stop after the first chunk
    gen.close()
    assert len(p.history) == 2
    assert len(p.mistakes.load()) == 1


def test_tts_failure_yields_silence(make_pipeline):
    class BrokenTTS(FakeTTS):
        def synthesize(self, text):
            raise RuntimeError("no voice")

    p = make_pipeline(tts=BrokenTTS())
    chunks = list(p.handle(AUDIO))
    assert chunks and all(not c.any() for _, c in chunks)
    assert value(p.metrics, "teacher_errors_total", {"stage": "tts"}) == 1


def test_parse_ollama_response_dict_and_object():
    raw = {
        "message": {"role": "assistant", "content": "  Hello!  "},
        "prompt_eval_count": 50,
        "eval_count": 20,
        "eval_duration": 2_000_000_000,
    }
    r = parse_response(raw)
    assert r.text == "Hello!"
    assert r.tokens_per_second == 10

    class Obj:
        message = type("M", (), {"content": "Hi"})()
        prompt_eval_count = None
        eval_count = 4
        eval_duration = None

    r = parse_response(Obj())
    assert (r.text, r.prompt_tokens, r.completion_tokens, r.tokens_per_second) == ("Hi", 0, 4, 0)


def test_warns_when_prompt_nearly_fills_context(make_pipeline):
    from loguru import logger

    messages = []
    sink = logger.add(lambda m: messages.append(m.record["message"]), level="WARNING")
    try:
        # FakeLLM reports 120 prompt tokens -> 120 >= 0.9 * 128
        list(make_pipeline(context_window=128).handle(AUDIO))
        assert any("context window" in m for m in messages)

        messages.clear()
        list(make_pipeline(context_window=4096).handle(AUDIO))
        assert not any("context window" in m for m in messages)
    finally:
        logger.remove(sink)
