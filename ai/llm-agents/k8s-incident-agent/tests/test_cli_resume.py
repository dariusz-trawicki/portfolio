"""An interrupted investigation (e.g. a model API error) can be resumed from its checkpoint
without collecting the evidence again."""

import re

from langchain_core.runnables import RunnableLambda
from typer.testing import CliRunner

import incident_agent.cli as cli
from test_graph import FIXTURE, ScriptedLLM, ai


class BrokenLLM(ScriptedLLM):
    def bind_tools(self, tools):
        def boom(_):
            raise RuntimeError("400 `temperature` is deprecated for this model.")
        return RunnableLambda(boom)


def test_failure_then_resume(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKPOINT_DB", str(tmp_path / "cp.sqlite"))
    args = ["--backend", "fake", "--fixture", str(FIXTURE), "--out-dir", str(tmp_path)]
    runner = CliRunner()

    monkeypatch.setattr(cli, "_llm", lambda s: BrokenLLM([]))
    r1 = runner.invoke(cli.app, ["investigate", *args])
    assert r1.exit_code == 1
    assert "Investigation interrupted" in r1.output
    thread = re.search(r"--resume (\S+)", r1.output).group(1)

    monkeypatch.setattr(cli, "_llm", lambda s: ScriptedLLM([ai("That is enough.")]))
    r2 = runner.invoke(cli.app, ["investigate", "--resume", thread, *args])
    assert r2.exit_code == 0, r2.output
    assert "resuming from: investigate" in r2.output
    assert "gather_" not in r2.output          # evidence is not collected a second time
    assert list(tmp_path.glob("*-checkout.md"))


def test_temperature_only_sent_when_configured(monkeypatch):
    from incident_agent.config import Settings
    monkeypatch.delenv("AGENT_TEMPERATURE", raising=False)
    assert Settings().temperature is None
    monkeypatch.setenv("AGENT_TEMPERATURE", "0")
    assert Settings().temperature == 0.0
