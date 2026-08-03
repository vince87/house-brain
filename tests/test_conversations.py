from pathlib import Path

from house_brain.conversations import ConversationStore


def test_conversation_store_keeps_bounded_ordered_history(
    tmp_path: Path,
) -> None:
    store = ConversationStore(str(tmp_path / "memory.db"))

    store.add_exchange("kitchen", "Prima domanda", "Prima risposta")
    store.add_exchange("kitchen", "Seconda domanda", "Seconda risposta")
    store.add_exchange("other", "Messaggio separato", "Risposta separata")

    history = store.history("kitchen", limit=3)

    assert [message.content for message in history] == [
        "Prima risposta",
        "Seconda domanda",
        "Seconda risposta",
    ]
    assert all(message.session_id == "kitchen" for message in history)
    assert store.clear("kitchen") == 4
    assert store.history("kitchen") == []
    assert len(store.history("other")) == 2
