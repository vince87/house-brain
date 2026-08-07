import asyncio
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException

from house_brain import main as main_module
from house_brain.actions import ActionRequest
from house_brain.agent import AgentResponse
from house_brain.autonomy import load_autonomy_policy
from house_brain.config import Settings
from house_brain.conversations import ConversationStore
from house_brain.events import AgentEventRequest, EventStore
from house_brain.memory import MemoryStore


class StubHomeAssistantClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str,
        data: dict[str, Any],
    ) -> list[object]:
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": data,
            }
        )
        return []


def _settings(tmp_path: Path):
    policy_path = tmp_path / "autonomy.yaml"
    policy_path.write_text(
        """
version: 2
entities:
  include:
    - entity_id: lock.example_front_door
      code: "2468"
  exclude: []
""".lstrip()
    )
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        memory_database_path=str(tmp_path / "memory.db"),
        autonomy_policy=load_autonomy_policy(policy_path),
        autonomous_execution_enabled=False,
    )


def test_direct_action_uses_same_entity_code(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    action = ActionRequest(
        domain="lock",
        service="unlock",
        entity_id="lock.example_front_door",
        dry_run=True,
    )

    result = asyncio.run(
        main_module.perform_action(
            action,
            StubHomeAssistantClient(),
            settings,
            "2468",
        )
    )
    assert result.status == "simulated"

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            main_module.perform_action(
                action,
                StubHomeAssistantClient(),
                settings,
                "9999",
            )
        )
    assert error.value.status_code == 403
    assert "valid authorization code" in str(error.value.detail)


def test_event_code_is_redacted_and_passed_to_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_agent(request, *args, **kwargs):
        captured["message"] = request.message
        captured["codes"] = kwargs["authorization_codes"]
        return AgentResponse(
            response="ok",
            session_id=request.session_id,
            model="test",
            iterations=1,
            tools_used=[],
            tool_trace=[],
        )

    monkeypatch.setattr(main_module, "run_agent", fake_run_agent)
    settings = _settings(tmp_path)
    database = str(tmp_path / "memory.db")
    store = EventStore(database)

    result = asyncio.run(
        main_module.handle_agent_event(
            AgentEventRequest(
                event_type="manual_lock_test",
                source="test",
                mode="simulate",
                instruction="Sblocca ingresso, codice: 2468",
                context={},
            ),
            StubHomeAssistantClient(),
            MemoryStore(database),
            ConversationStore(database),
            store,
            settings,
        )
    )

    assert result.response == "ok"
    assert captured["codes"] == ("2468",)
    assert "2468" not in str(captured["message"])
    record = store.get(result.event_id)
    assert record is not None
    assert "2468" not in record.instruction
    assert "[fornito]" in record.instruction
