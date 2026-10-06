"""OllamaLLM with a fake client (no Ollama server needed)."""

from english_teacher.config import LLMConfig
from english_teacher.llm import OllamaLLM


class FakeClient:
    def __init__(self, fail=False):
        self.fail = fail
        self.generate_calls = []
        self.chat_calls = []

    def generate(self, **kwargs):
        if self.fail:
            raise ConnectionError("ollama down")
        self.generate_calls.append(kwargs)
        return {}

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        return {"message": {"content": "Hi"}}


def make_llm(client):
    llm = OllamaLLM(LLMConfig(model="m", keep_alive="10m"))
    llm.client = client
    return llm


def test_warmup_loads_model_with_empty_prompt_and_keep_alive():
    client = FakeClient()
    assert make_llm(client).warmup() is True
    assert client.generate_calls == [{"model": "m", "prompt": "", "keep_alive": "10m"}]


def test_warmup_never_raises():
    assert make_llm(FakeClient(fail=True)).warmup() is False


def test_chat_passes_keep_alive():
    client = FakeClient()
    make_llm(client).chat([{"role": "user", "content": "hi"}])
    assert client.chat_calls[0]["keep_alive"] == "10m"
