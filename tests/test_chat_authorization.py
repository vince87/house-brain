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
    _authorized_code_instruction,
    _authorized_entity_context,
    _autonomy_policy_instruction,
    _execute_tool,
    _failed_action_response,
    _invalid_action_requires_retry,
    _normalize_action_service_names,
    _remove_authorization_placeholder,
    _request_targets_policy_protected_entity,
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
            "lock.example_front_door": "Example Front Door",
            "lock.example_garage_door": "Example Garage Door",
        }
        return SimpleNamespace(
            entity_id=entity_id,
            state="locked",
            attributes={"friendly_name": names[entity_id]},
        )


class DeviceCodeHomeAssistantClient(StubHomeAssistantClient):
    async def prepare_service_data(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict[str, Any],
        *,
        supplied_codes: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        assert domain == "lock"
        assert service == "unlock"
        assert entity_id == "lock.example_front_door"
        assert data == {}
        assert supplied_codes == ("2468",)
        return {"code": supplied_codes[-1]}


def _catalog(tmp_path: Path):
    path = tmp_path / "autonomy.yaml"
    path.write_text(
        """
version: 2
entities:
  include:
    - entity_id: lock.example_front_door
      code: "2468"
    - entity_id: lock.example_garage_door
      code: "8642"
    - lock.example_internal_door
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
    message, codes = extract_authorization_codes("Sblocca ingresso, codice: 2468")

    assert message == "Sblocca ingresso, codice: [authorization provided]"
    assert codes == ("2468",)
    assert "2468" not in message


def test_multiple_codes_are_redacted_and_deduplicated() -> None:
    message, codes = extract_authorization_codes(
        "Codice: 2468 e codice: 8642; ripeto codice: 2468"
    )

    assert "2468" not in message
    assert "8642" not in message
    assert codes == ("2468", "8642")


@pytest.mark.parametrize("code", ["2468", "1233"])
def test_natural_trailing_numeric_code_is_extracted(code: str) -> None:
    message, codes = extract_authorization_codes(
        f"Simula lo sblocco di Example Front Door {code}"
    )

    assert code not in message
    assert message.endswith("[authorization provided]")
    assert codes == (code,)


def test_unrelated_year_is_not_treated_as_authorization_code() -> None:
    message, codes = extract_authorization_codes("Cosa succederà nel 2026?")

    assert message == "Cosa succederà nel 2026?"
    assert codes == ()


def test_invalid_code_marker_is_redacted_but_not_accepted() -> None:
    message, codes = extract_authorization_codes("Sblocca ingresso, codice: x")

    assert message == "Sblocca ingresso, codice: [authorization provided]"
    assert codes == ()


def test_policy_resolves_reserved_chat_command(tmp_path: Path) -> None:
    policy = _catalog(tmp_path).resolve_chat()

    assert policy is not None
    assert policy.allowed_modes == frozenset({"observe", "simulate", "execute"})
    assert set(policy.entity_codes) == {
        "lock.example_front_door",
        "lock.example_garage_door",
    }


def test_policy_resolves_code_to_entity_without_exposing_it(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    assert policy is not None

    assert policy.authorized_entities(("2468",)) == frozenset(
        {"lock.example_front_door"}
    )
    assert policy.authorized_entities(("9999",)) == frozenset()
    instruction = _authorized_code_instruction(frozenset({"lock.example_front_door"}))
    assert "lock.example_front_door" in instruction
    assert "2468" not in instruction


def test_only_policy_protected_target_forces_code_validation(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    assert policy is not None

    assert _request_targets_policy_protected_entity(
        policy,
        pre_resolution={
            "status": "resolved",
            "entity": {"entity_id": "lock.example_front_door"},
        },
        explicit_entity_ids=frozenset(),
    )
    assert not _request_targets_policy_protected_entity(
        policy,
        pre_resolution={
            "status": "resolved",
            "entity": {"entity_id": "lock.example_internal_door"},
        },
        explicit_entity_ids=frozenset(),
    )


def test_correct_code_allows_chat_simulation(tmp_path: Path) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    client = StubHomeAssistantClient()

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "lock",
                "service": "unlock",
                "entity_id": "lock.example_front_door",
                "dry_run": True,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=False),
            authorization_codes=("2468",),
        )
    )

    assert result["status"] == "simulated"
    assert client.calls == []


@pytest.mark.parametrize("codes", [(), ("0000",), ("8642",)])
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
                    "entity_id": "lock.example_front_door",
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
                    "entity_id": "lock.example_front_door",
                    "dry_run": False,
                },
                StubHomeAssistantClient(),
                MemoryStore(str(tmp_path / "memory.db")),
                autonomy_policy=policy,
                settings=_settings(tmp_path, execution_enabled=False),
                authorization_codes=("2468",),
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
                "entity_id": "lock.example_front_door",
                "dry_run": False,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=True),
            authorization_codes=("2468",),
        )
    )

    assert result["status"] == "executed"
    assert client.calls == [
        {
            "domain": "lock",
            "service": "unlock",
            "entity_id": "lock.example_front_door",
            "data": {},
        }
    ]


def test_device_code_is_sent_to_home_assistant_but_not_returned(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    client = DeviceCodeHomeAssistantClient()

    result = asyncio.run(
        _execute_tool(
            "perform_action",
            {
                "domain": "lock",
                "service": "unlock",
                "entity_id": "lock.example_front_door",
                "dry_run": False,
            },
            client,
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=True),
            authorization_codes=("2468",),
        )
    )

    assert result["status"] == "executed"
    assert result["data"] == {}
    assert client.calls[0]["data"] == {"code": "2468"}


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
                "entity_id": "lock.example_internal_door",
                "dry_run": True,
            },
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            autonomy_policy=policy,
            settings=_settings(tmp_path, execution_enabled=False),
        )
    )

    assert result["status"] == "simulated"


def test_prompt_delegates_authorization_without_exposing_code(
    tmp_path: Path,
) -> None:
    policy = _catalog(tmp_path).resolve_chat()
    prompt = _autonomy_policy_instruction(policy)

    assert "authorization is handled only by the server" in prompt
    assert "Controllable entities" in prompt
    assert "lock.example_front_door" in prompt
    assert "2468" not in prompt
    assert "8642" not in prompt


def test_policy_repr_does_not_expose_codes(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    policy = catalog.resolve_chat()

    assert "2468" not in repr(catalog)
    assert "8642" not in repr(catalog)
    assert "2468" not in repr(policy)
    assert "8642" not in repr(policy)


def test_invalid_entity_code_configuration_fails_startup(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.yaml"
    path.write_text(
        """
version: 2
entities:
  include:
    - entity_id: lock.example_front_door
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
                message="Sblocca ingresso, codice: 2468",
                session_id="test",
            ),
            StubHomeAssistantClient(),
            MemoryStore(str(tmp_path / "memory.db")),
            object(),
            settings,
        )
    )

    assert response.response == "ok"
    assert captured["message"] == ("Sblocca ingresso, codice: [authorization provided]")
    assert captured["authorization_codes"] == ("2468",)
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

    assert "Authoritative inventory" in context
    assert (
        "lock.example_front_door; state=locked; friendly_name=Example Front Door"
    ) in context
    assert (
        "lock.example_garage_door; state=locked; friendly_name=Example Garage Door"
    ) in context


def test_list_tool_outcome_reports_result_count() -> None:
    assert _tool_outcome([]) == "completed:0_items"
    assert _tool_outcome([{"entity_id": "lock.example_front_door"}]) == (
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
        "entity_id": "lock.example_front_door",
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
            authorization_codes=("2468",),
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
        "entity_id": "lock.example_front_door",
        "data": {"code": "2468"},
        "dry_run": True,
    }

    _remove_authorization_placeholder(arguments, policy)

    assert arguments["data"] == {"code": "2468"}


def test_supplied_code_requires_an_action_tool_before_final_answer() -> None:
    assert _authorization_requires_action_validation(True, [])
    assert not _authorization_requires_action_validation(False, [])
    assert not _authorization_requires_action_validation(
        True,
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


def test_malformed_action_is_retried_before_final_response() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={"service": "lock.unlock"},
            status="failed",
            outcome="rejected",
            error="ActionPolicyError: Invalid action service",
        )
    ]

    assert _invalid_action_requires_retry(trace)
    trace.append(
        ToolAuditRecord(
            sequence=2,
            tool="perform_action",
            arguments={"service": "unlock"},
            status="completed",
            outcome="simulated",
        )
    )
    assert not _invalid_action_requires_retry(trace)


def test_nonexistent_home_assistant_service_is_retried() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={
                "domain": "alarm_control_panel",
                "service": "alarm_arm_action",
                "entity_id": "alarm_control_panel.example_home",
            },
            status="failed",
            outcome="rejected",
            error=(
                "ServiceCatalogError: Home Assistant service does not exist: "
                "alarm_control_panel.alarm_arm_action"
            ),
        )
    ]

    assert _invalid_action_requires_retry(trace)


def test_required_device_code_has_specific_localized_rejection() -> None:
    trace = [
        ToolAuditRecord(
            sequence=1,
            tool="perform_action",
            arguments={
                "domain": "alarm_control_panel",
                "service": "alarm_disarm",
                "entity_id": "alarm_control_panel.example_home",
            },
            status="failed",
            outcome="rejected",
            error=(
                "ServiceCatalogError: Home Assistant service parameter is "
                "required: code"
            ),
        )
    ]

    response = _failed_action_response(trace, "it")

    assert response is not None
    assert "dispositivo richiede il proprio codice Home Assistant" in response


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
        "entity_id": "lock.example_front_door",
    }

    _normalize_action_service_names(arguments)

    assert arguments["service"] == "unlock"


def test_batch_domain_prefixed_services_are_normalized() -> None:
    arguments = {
        "actions": [
            {
                "domain": "lock",
                "service": "lock.unlock",
                "entity_id": "lock.example_front_door",
            },
            {
                "domain": "button",
                "service": "button.press",
                "entity_id": "button.example_gate",
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
        "entity_id": "lock.example_front_door",
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
