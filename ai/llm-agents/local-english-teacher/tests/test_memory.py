import json

from english_teacher.memory import ConversationHistory, MistakeStore


def test_history_sliding_window():
    h = ConversationHistory(max_messages=4)
    for i in range(5):
        h.add_exchange(f"user {i}", f"assistant {i}")
    snap = h.snapshot()
    assert len(snap) == 4
    assert snap[0] == {"role": "user", "content": "user 3"}
    assert snap[-1] == {"role": "assistant", "content": "assistant 4"}


def test_history_never_grows_unbounded():
    h = ConversationHistory(max_messages=4)
    for i in range(100):
        h.add_exchange(str(i), str(i))
    assert len(h) <= 8


def test_history_zero_window_is_stateless():
    h = ConversationHistory(max_messages=0)
    h.add_exchange("a", "b")
    assert h.snapshot() == []


def test_mistake_store_roundtrip(tmp_path):
    store = MistakeStore(tmp_path / "nested" / "mistakes.json")
    assert store.load() == []
    store.add("I goed", "I went")
    store.add("she don't", "she doesn't")

    data = json.loads((tmp_path / "nested" / "mistakes.json").read_text())
    assert [m["wrong"] for m in data] == ["I goed", "she don't"]
    assert store.recent(1)[0]["correct"] == "she doesn't"
    assert store.recent(0) == []

    store.reset()
    assert store.load() == []


def test_mistake_store_survives_corrupted_file(tmp_path):
    path = tmp_path / "mistakes.json"
    path.write_text("{not json")
    assert MistakeStore(path).load() == []


def test_empty_mistakes_file_is_treated_as_no_mistakes(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("")
    store = MistakeStore(path)
    assert store.load() == []
    store.add("a", "b")
    assert [m["wrong"] for m in store.load()] == ["a"]


def test_corrupt_mistakes_file_is_backed_up_not_lost(tmp_path):
    path = tmp_path / "m.json"
    path.write_text("{not json")
    store = MistakeStore(path)
    store.add("a", "b")
    assert (tmp_path / "m.json.corrupt").read_text() == "{not json"
    assert [m["wrong"] for m in store.load()] == ["a"]
