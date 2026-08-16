import sqlite3
from pathlib import Path

from house_brain.conversations import ConversationStore
from house_brain.events import ToolAuditRecord


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


def test_conversation_store_persists_assistant_action_audit(tmp_path: Path) -> None:
    store = ConversationStore(str(tmp_path / "memory.db"))
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={
                "domain": "light",
                "service": "turn_off",
                "entity_id": "light.example_room",
            },
            status="completed",
            outcome="simulated",
        )
    ]

    store.add_exchange(
        "audit",
        "Turn it off",
        "Simulated.",
        assistant_tool_trace=trace,
    )

    history = store.history("audit")
    assert history[0].tool_trace == []
    assert history[1].tool_trace[0].outcome == "simulated"
    assert history[1].tool_trace[0].arguments["entity_id"] == "light.example_room"


def test_existing_conversation_database_is_migrated(tmp_path: Path) -> None:
    path = tmp_path / "memory.db"
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE conversation_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

    store = ConversationStore(str(path))
    store.add_exchange("migrated", "Question", "Answer")

    assert [item.content for item in store.history("migrated")] == [
        "Question",
        "Answer",
    ]
