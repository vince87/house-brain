import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from house_brain import main as main_module
from house_brain.agent import (
    AgentRequest,
    AgentResponse,
    _authorized_entity_context,
    _autonomy_policy_instruction,
    _execute_tool,
    _tool_outcome,
)
from house_brain.authorization import extract_authorization_codes
from house_brain.autonomy import AutonomyPolicyError, load_autonomy_policy
from house_brain.config import Settings
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

    async def get_entity(self, entity_id: str):
        names = {
            "lock.ingresso": "Portoncino Casa",
            "lock.garage": "Porta Garage",
        }
        return SimpleNamespace(
            entity_id=entity_id,
            state="locked",
            attributes={"friendly_name": names[entity_id]},
        )


def _catalog(tmp_path: Path):
    path = tmp_path / "autonomy.yaml"
    path.write_text(
        """
version: 1
events:
  chat_command:
    modes: [simulate, execute]
    max_actions: 2
    actions:
      lock.unlock:
        entities:
          - lock.ingresso
          - lock.garage
        authorization:
          codes:
            lock.ingresso: "1234"
            lock.garage: "9876"
      lock.lock:
        entities:
          - lock.ingresso
""".lstrip()
    )
    return load_autonomy_policy(path)


def _settings(tmp_path: Path, *, execution_enabled: bool) -> Settings:
    return Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        memory_database_path=str(tmp_path / "memory.db"),
        autonomous_execution_enabled=execution_enabled,
    )


def test_chat_code_is_redacted_before_llm_or_persistence() -> None:
    message, codes = extract_authorization_codes(
        "Sblocca ingresso, codice: 1234"
    )

    assert message == "Sblocca ingresso, codice: [fornito]"
    assert codes == ("1234",)
    assert "1234" not in message


def test_multiple_codes_are_redacted_and_deduplicated() -> None:
    message, codes = extract_authorization_codes(
        "Codice: 1234 e codice: 9876; ripeto codice: 1234"
    )

    assert "1234" not in message
    assert "9876" not in message
    assert codes == ("1234", "9876")


def test_invalid_code_marker_is_redacted_but_not_accepted() -> None:
    message, codes = extract_authorization_codes(
        "Sblocca ingresso, codice: x"
    )

    assert message == "Sblocca ingresso, codice: [fornito]"
    assert codes == ()


def test_policy_resolves_reserved_chat_command(tmp_path: Path) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    assert policy is not None
    assert policy.allowed_modes == frozenset({"simulate", "execute"})
    assert set(policy.action_codes) == {
        "lock.unlock:lock.ingresso",
        "lock.unlock:lock.garage",
    }


def test_correct_code_allows_chat_simulation(tmp_path: Path) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    client = StubHomeAssistantClient()

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "lock",
                "service": "unlock",
                "entity_id": "lock.ingresso",
                "dry_run": True,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=False),
            authorization_codes=("1234",),
        )
    )

    assert result["status"] == "simulated"
    assert client.calls == []


@pytest.mark.parametrize("codes", [(), ("0000",), ("9876",)])
def test_missing_wrong_or_other_device_code_is_rejected(
    tmp_path: Path,
    codes: tuple[str, ...],
) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    with pytest.raises(
        AutonomyPolicyError,
        match="requires a valid authorization code",
    ):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "lock",
                    "service": "unlock",
                    "entity_id": "lock.ingresso",
                    "dry_run": True,
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                autonomy_policy=policy,
                settings=_settings(tmp_path, execution_enabled=False),
                authorization_codes=codes,
            )
        )


def test_correct_code_cannot_bypass_global_kill_switch(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    with pytest.raises(AutonomyPolicyError, match="global kill switch"):
        asyncio.run(
            _execute_tool(
                "perform_action",
                {
                    "domain": "lock",
                    "service": "unlock",
                    "entity_id": "lock.ingresso",
                    "dry_run": False,
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                autonomy_policy=policy,
                settings=_settings(tmp_path, execution_enabled=False),
                authorization_codes=("1234",),
            )
        )


def test_correct_code_and_kill_switch_allow_real_chat_action(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    client = StubHomeAssistantClient()

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "lock",
                "service": "unlock",
                "entity_id": "lock.ingresso",
                "dry_run": False,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=True),
            authorization_codes=("1234",),
        )
    )

    assert result["status"] == "executed"
    assert client.calls == [
        {
            "domain": "lock",
            "service": "unlock",
            "entity_id": "lock.ingresso",
            "data": {},
        }
    ]


def test_action_without_code_requirement_still_uses_policy(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "lock",
                "service": "lock",
                "entity_id": "lock.ingresso",
                "dry_run": True,
            },
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=False),
        )
    )

    assert result["status"] == "simulated"


def test_prompt_discloses_requirement_but_not_code(tmp_path: Path) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    prompt = _autonomy_policy_instruction(policy)

    assert "codice richiesto" in prompt
    assert "non usare search_entities per riscoprirli" in prompt
    assert "usa direttamente il relativo entity_id" in prompt
    assert "1234" not in prompt
    assert "9876" not in prompt


def test_policy_repr_does_not_expose_codes(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    policy = catalog.resolve_chat()

    assert "1234" not in repr(catalog)
    assert "9876" not in repr(catalog)
    assert "1234" not in repr(policy)
    assert "9876" not in repr(policy)


@pytest.mark.parametrize(
    "authorization",
    [
        "authorization: []",
        "authorization:\n          unknown: true",
        "authorization:\n          codes: []",
        (
            "authorization:\n"
            "          codes:\n"
            "            lock.non_dichiarata: '1234'"
        ),
        (
            "authorization:\n"
            "          codes:\n"
            "            lock.ingresso: 'x'"
        ),
    ],
)
def test_invalid_authorization_configuration_fails_startup(
    tmp_path: Path,
    authorization: str,
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        f"""
version: 1
events:
  chat_command:
    modes: [simulate]
    actions:
      lock.unlock:
        entities: [lock.ingresso]
        {authorization}
""".lstrip()
    )

    with pytest.raises(AutonomyPolicyError):
        load_autonomy_policy(path)


def test_chat_endpoint_never_passes_raw_code_to_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    async def fake_run_agent(
        request,
        settings,
        client,
        store,
        conversations,
        **kwargs,
    ):
        captured["message"] = request.message
        captured["authorization_codes"] = kwargs["authorization_codes"]
        captured["policy"] = kwargs["autonomy_policy"]
        return AgentResponse(
            response="ok",
            session_id=request.session_id,
            model=settings.ollama_model,
            iterations=1,
            tools_used=[],
            tool_trace=[],
        )

    monkeypatch.setattr(main_module, "run_agent", fake_run_agent)
    settings = Settings(
        home_assistant_url="http://homeassistant.test:8123",
        home_assistant_token="secret",
        memory_database_path=str(tmp_path / "memory.db"),
        autonomy_policy=_catalog(tmp_path),
    )

    response = asyncio.run(
        main_module.agent_chat(
            AgentRequest(
                message="Sblocca ingresso, codice: 1234",
                session_id="test",
            ),
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            object(),
            settings,
        )
    )

    assert response.response == "ok"
    assert captured["message"] == "Sblocca ingresso, codice: [fornito]"
    assert captured["authorization_codes"] == ("1234",)
    assert captured["policy"] is not None


def test_authorized_entity_context_uses_real_home_assistant_metadata(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    context = asyncio.run(
        _authorized_entity_context(
            policy,
            StubHomeAssistantClient(),
        )
    )

    assert "Inventario autorevole" in context
    assert "lock.ingresso; state=locked; friendly_name=Portoncino Casa" in context
    assert "lock.garage; state=locked; friendly_name=Porta Garage" in context


def test_list_tool_outcome_reports_result_count() -> None:
    assert _tool_outcome([]) == "completed:0_items"
    assert _tool_outcome([{"entity_id": "lock.ingresso"}]) == (
        "completed:1_items"
    )
