import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from house_brain import main as main_module
from house_brain.agent import (
    AgentRequest,
    AgentResponse,
    _authorization_requires_action_validation,
    _authorized_entity_context,
    _autonomy_policy_instruction,
    _execute_tool,
    _failed_action_response,
    _normalize_action_service_names,
    _remove_authorization_placeholder,
    _tool_outcome,
)
from house_brain.authorization import extract_authorization_codes
from house_brain.autonomy import AutonomyPolicyError, load_autonomy_policy
from house_brain.config import Settings
from house_brain.events import ToolAuditRecord
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
version: 2
entities:
  include:
    - entity_id: lock.ingresso
      code: "1234"
    - entity_id: lock.garage
      code: "9876"
    - lock.porta_interna
  exclude: []
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
    assert policy.allowed_modes == frozenset({"observe", "simulate", "execute"})
    assert set(policy.entity_codes) == {"lock.ingresso", "lock.garage"}


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
                "entity_id": "lock.porta_interna",
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
    assert "Entità controllabili" in prompt
    assert "lock.ingresso" in prompt
    assert "1234" not in prompt
    assert "9876" not in prompt


def test_policy_repr_does_not_expose_codes(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    policy = catalog.resolve_chat()

    assert "1234" not in repr(catalog)
    assert "9876" not in repr(catalog)
    assert "1234" not in repr(policy)
    assert "9876" not in repr(policy)


def test_invalid_entity_code_configuration_fails_startup(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """
version: 2
entities:
  include:
    - entity_id: lock.ingresso
      code: x
  exclude: []
""".lstrip()
    )

    with pytest.raises(AutonomyPolicyError, match="Invalid authorization code"):
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


def test_authorization_placeholder_is_not_sent_as_service_data(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    client = StubHomeAssistantClient()
    arguments = {
        "domain": "lock",
        "service": "unlock",
        "entity_id": "lock.ingresso",
        "data": {"code": "[fornito]"},
        "dry_run": True,
    }

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            arguments,
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=False),
            authorization_codes=("1234",),
        )
    )

    assert result["status"] == "simulated"
    assert arguments["data"] == {}
    assert client.calls == []


def test_real_code_like_action_data_is_never_silently_removed(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    arguments = {
        "domain": "lock",
        "service": "unlock",
        "entity_id": "lock.ingresso",
        "data": {"code": "1234"},
        "dry_run": True,
    }

    _remove_authorization_placeholder(arguments, policy)

    assert arguments["data"] == {"code": "1234"}


def test_supplied_code_requires_an_action_tool_before_final_answer() -> None:
    assert _authorization_requires_action_validation(("1234",), [])
    assert not _authorization_requires_action_validation((), [])
    assert not _authorization_requires_action_validation(
        ("1234",),
        [
            ToolAuditRecord(
                sequence=1,
                tool="perform_action",
                arguments={"domain": "lock"},
                status="failed",
                outcome="rejected",
                error="AutonomyPolicyError",
            )
        ],
    )


def test_all_failed_action_tools_force_truthful_response() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={"domain": "lock"},
            status="failed",
            outcome="rejected",
            error="AutonomyPolicyError",
        ),
        ToolAuditRecord(
            sequence=2,
            tool="perform_action",
            arguments={"domain": "lock"},
            status="failed",
            outcome="rejected",
            error="AutonomyPolicyError",
        ),
    ]

    assert _failed_action_response(trace) == (
        "Il piano è stato respinto perché la policy del server ha rifiutato "
        "il piano; nessuna azione è stata simulata o eseguita."
    )


def test_one_successful_action_preserves_model_response() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={"domain": "lock"},
            status="failed",
            outcome="rejected",
            error="ValidationError",
        ),
        ToolAuditRecord(
            sequence=2,
            tool="perform_action",
            arguments={"domain": "lock"},
            status="completed",
            outcome="simulated",
        ),
    ]

    assert _failed_action_response(trace) is None


def test_domain_prefixed_service_is_normalized_before_validation() -> None:
    arguments = {
        "domain": "lock",
        "service": "lock.unlock",
        "entity_id": "lock.ingresso",
    }

    _normalize_action_service_names(arguments)

    assert arguments["service"] == "unlock"


def test_batch_domain_prefixed_services_are_normalized() -> None:
    arguments = {
        "actions": [
            {
                "domain": "lock",
                "service": "lock.unlock",
                "entity_id": "lock.ingresso",
            },
            {
                "domain": "button",
                "service": "button.press",
                "entity_id": "button.cancello",
            },
        ]
    }

    _normalize_action_service_names(arguments)

    assert [item["service"] for item in arguments["actions"]] == [
        "unlock",
        "press",
    ]


def test_unrelated_or_ambiguous_service_name_is_not_rewritten() -> None:
    arguments = {
        "domain": "lock",
        "service": "button.press",
        "entity_id": "lock.ingresso",
    }

    _normalize_action_service_names(arguments)

    assert arguments["service"] == "button.press"


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            "AutonomyPolicyError: Autonomous action requires a valid "
            "authorization code",
            "il codice è mancante, malformato o errato",
        ),
        (
            "AutonomyPolicyError: Autonomous execution is disabled by the "
            "global kill switch",
            "l'esecuzione reale è disabilitata dal kill switch",
        ),
        (
            "AutonomyPolicyError: Autonomous action is not allowlisted",
            "l'azione richiesta non è autorizzata dalla policy",
        ),
        (
            "AutonomyPolicyError: Autonomous parameter value is not allowed",
            "un valore richiesto non è autorizzato dalla policy",
        ),
    ],
)
def test_failed_action_response_explains_sanitized_reason(
    error: str,
    reason: str,
) -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={"domain": "lock"},
            status="failed",
            outcome="rejected",
            error=error,
        )
    ]

    response = _failed_action_response(trace)

    assert response is not None
    assert reason in response
    assert "nessuna azione è stata simulata o eseguita" in response
