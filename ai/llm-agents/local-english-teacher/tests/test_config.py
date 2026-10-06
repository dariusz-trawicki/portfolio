import pytest

from english_teacher.config import env_overrides, load_config


def test_defaults():
    cfg = load_config(environ={})
    assert cfg.llm.model == "gemma3:4b"
    assert cfg.teacher.level == "B1"
    assert cfg.server.metrics_enabled is True


def test_precedence_yaml_env_cli(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text("llm:\n  model: from-yaml\n  num_ctx: 2048\nteacher:\n  level: a2\n")

    cfg = load_config(path, environ={})
    assert cfg.llm.model == "from-yaml"
    assert cfg.llm.num_ctx == 2048
    assert cfg.teacher.level == "A2"  # normalised to upper case

    env = {"TEACHER_LLM__MODEL": "from-env", "TEACHER_LLM__NUM_CTX": "8192"}
    cfg = load_config(path, environ=env)
    assert cfg.llm.model == "from-env"
    assert cfg.llm.num_ctx == 8192  # coerced from string

    cfg = load_config(path, environ=env, cli_overrides={"llm": {"model": "from-cli"}})
    assert cfg.llm.model == "from-cli"


def test_cli_none_values_are_ignored():
    cfg = load_config(environ={}, cli_overrides={"llm": {"model": None}})
    assert cfg.llm.model == "gemma3:4b"


def test_bool_coercion_from_env():
    cfg = load_config(environ={"TEACHER_SERVER__METRICS_ENABLED": "false"})
    assert cfg.server.metrics_enabled is False


def test_ollama_host_env_is_respected():
    cfg = load_config(environ={"OLLAMA_HOST": "ollama:11434"})
    assert cfg.llm.host == "http://ollama:11434"


def test_env_overrides_parsing():
    out = env_overrides({"TEACHER_STT__MODEL_SIZE": "medium", "OTHER": "x", "TEACHER_X": "y"})
    assert out == {"stt": {"model_size": "medium"}}


@pytest.mark.parametrize(
    "env",
    [
        {"TEACHER_TEACHER__LEVEL": "Z9"},
        {"TEACHER_TTS__BACKEND": "espeak"},
        {"TEACHER_LLM__UNKNOWN": "1"},
        {"TEACHER_NOPE__MODEL": "1"},
        {"TEACHER_LLM__NUM_CTX": "100", "TEACHER_LLM__NUM_PREDICT": "200"},
    ],
)
def test_invalid_config_raises(env):
    with pytest.raises(ValueError):
        load_config(environ=env)


def test_missing_config_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "missing.yaml", environ={})


def test_repo_config_yaml_is_valid():
    cfg = load_config("config.yaml", environ={})
    assert cfg.teacher.level in ("A1", "A2", "B1", "B2", "C1", "C2")
