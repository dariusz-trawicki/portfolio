import pytest

from english_teacher.text import clean_for_tts, extract_correction


@pytest.mark.parametrize(
    "reply, expected",
    [
        (
            'Nice! Small correction: you said "I goed", better is "I went". Where did you go?',
            ("I goed", "I went"),
        ),
        (
            "Small correction: you said she don't like coffee, better would be she doesn't "
            "like coffee.",
            ("she don't like coffee", "she doesn't like coffee"),
        ),
        (
            "small correction: You said “I am agree”; it's better to say “I agree”.",
            ("I am agree", "I agree"),
        ),
    ],
)
def test_extract_correction_variants(reply, expected):
    assert extract_correction(reply) == expected


@pytest.mark.parametrize(
    "reply",
    [
        "Great answer! What tools do you use for model monitoring?",
        'Small correction: you said "I agree", better is "I agree".',  # same text -> ignored
        "",
    ],
)
def test_extract_correction_none(reply):
    assert extract_correction(reply) is None


def test_clean_for_tts_removes_markdown_and_emoji():
    raw = "**Great** job! 😊 Let's talk about `MLflow` and #MLOps."
    assert clean_for_tts(raw) == "Great job! Let's talk about MLflow and MLOps."


def test_clean_for_tts_collapses_whitespace():
    assert clean_for_tts("Hello,\n\n  how   are you?") == "Hello, how are you?"
