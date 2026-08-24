from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from house_brain.action_plans import (
    ActionPlanConflictError,
    ActionPlanStore,
    PlannedActionInput,
    actions_from_simulation_trace,
    entity_matches_plan,
    planned_action,
)
from house_brain.agent import AgentResponse
from house_brain.autonomy import AutonomyPolicyCatalog, VisibilityPolicy
from house_brain.config import Settings, get_settings
from house_brain.events import ToolAuditRecord
from house_brain.home_assistant import HomeAssistantEntity
from house_brain.main import (
    app,
    get_action_plan_store,
    get_home_assistant_client,
)

ENTITY_ID = "light.example_room"


def _entity(state: str = "off", brightness: int = 0) -> HomeAssistantEntity:
    timestamp = datetime(2026, 8, 24, 8, 0, tzinfo=UTC)
    return HomeAssistantEntity(
        entity_id=ENTITY_ID,
        state=state,
        attributes={"friendly_name": "Example Room", "brightness": brightness},
        last_changed=timestamp,
        last_updated=timestamp,
        context={},
    )


def _input() -> PlannedActionInput:
    return PlannedActionInput(
        domain="light",
        service="turn_on",
        entity_id=ENTITY_ID,
        data={"brightness": 100},
        reason="Restore the requested lighting level",
    )


def test_plan_store_claims_once_and_records_outcome(tmp_path) -> None:
    store = ActionPlanStore(str(tmp_path / "plans.db"))
    action = planned_action(_input(), _entity())
    created = store.create(
        [action],
        expires_in_seconds=300,
        execution_enabled=True,
    )

    claimed = store.claim(created.plan_id)
    assert claimed.status == "executing"
    with pytest.raises(ActionPlanConflictError):
        store.claim(created.plan_id)

    finished = store.finish(created.plan_id, status="executed")
    assert finished.status == "executed"
    assert store.get(created.plan_id).status == "executed"


def test_plan_store_rejects_only_pending_plan(tmp_path) -> None:
    store = ActionPlanStore(str(tmp_path / "plans.db"))
    created = store.create(
        [planned_action(_input(), _entity())],
        expires_in_seconds=300,
        execution_enabled=False,
    )

    assert store.reject(created.plan_id).status == "rejected"
    with pytest.raises(ActionPlanConflictError):
        store.reject(created.plan_id)


def test_plan_fingerprint_detects_attribute_or_state_changes() -> None:
    planned = planned_action(_input(), _entity())

    assert entity_matches_plan(planned, _entity()) is True
    assert entity_matches_plan(planned, _entity(state="on")) is False
    assert entity_matches_plan(planned, _entity(brightness=20)) is False


def test_plan_never_accepts_codes_inside_persisted_action_data() -> None:
    protected = _input().model_copy(update={"data": {"code": "example-code"}})

    with pytest.raises(ValueError, match="supplied through headers"):
        planned_action(protected, _entity())


def test_plan_uses_only_successful_simulated_trace_actions() -> None:
    simulated = ToolAuditRecord(
        sequence=1,
        tool="perform_action",
        arguments={
            "domain": "light",
            "service": "turn_on",
            "entity_id": ENTITY_ID,
            "data": {"brightness": 100},
            "dry_run": True,
        },
        status="completed",
        outcome="simulated",
    )
    rejected = simulated.model_copy(
        update={"sequence": 2, "status": "failed", "outcome": "rejected"}
    )

    actions = actions_from_simulation_trace(
        [simulated, rejected, simulated.model_copy(update={"sequence": 3})],
        reason="Set the example light",
    )

    assert len(actions) == 1
    assert actions[0].entity_id == ENTITY_ID
    assert "dry_run" not in actions[0].model_dump()


def test_action_plan_documentation_covers_every_safety_gate() -> None:
    guide = Path("docs/action-plans.md").read_text(encoding="utf-8")

    for expected in (
        "tool_trace",
        "simulate",
        "AUTONOMOUS_EXECUTION_ENABLED=true",
        "invalidated",
        "una sola volta",
        "header",
        "/action-plans/from-request",
    ):
        assert expected in guide


class StubPlanClient:
    def __init__(self) -> None:
        self.entity = _entity()
        self.calls: list[dict[str, object]] = []

    async def ensure_accessible(self, entity_id: str) -> None:
        assert entity_id == ENTITY_ID

    async def prepare_service_data(
        self,
        domain: str,
        service: str,
        entity_id: str,
        data: dict[str, object],
        *,
        supplied_codes: tuple[str, ...] = (),
    ) -> dict[str, object]:
        assert (domain, service, entity_id) == (
            "light",
            "turn_on",
            ENTITY_ID,
        )
        return dict(data)

    async def get_entity(self, entity_id: str) -> HomeAssistantEntity:
        assert entity_id == ENTITY_ID
        return self.entity

    async def call_service(
        self,
        domain: str,
        service: str,
        *,
        entity_id: str,
        data: dict[str, object],
    ) -> dict[str, bool]:
        self.calls.append(
            {
                "domain": domain,
                "service": service,
                "entity_id": entity_id,
                "data": data,
            }
        )
        return {"called": True}


@pytest.fixture
def plan_api(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HOME_ASSISTANT_URL", "http://homeassistant.test:8123")
    monkeypatch.setenv("HOME_ASSISTANT_TOKEN", "secret")
    monkeypatch.setenv("HOUSE_BRAIN_API_KEY", "plan-api-key")
    get_settings.cache_clear()
    client = StubPlanClient()
    store = ActionPlanStore(str(tmp_path / "plans.db"))
    policy = AutonomyPolicyCatalog(
        visibility=VisibilityPolicy(visible_entities=frozenset({ENTITY_ID})),
        visible_entities=frozenset(),
        included_entities=frozenset({ENTITY_ID}),
        simple_entity_policy=True,
    )

    def settings(enabled: bool) -> Settings:
        return Settings(
            home_assistant_url="http://homeassistant.test:8123",
            home_assistant_token="secret",
            api_key="plan-api-key",
            autonomy_policy=policy,
            autonomous_execution_enabled=enabled,
            memory_database_path=str(tmp_path / "plans.db"),
        )

    active_settings = settings(True)

    async def override_client() -> StubPlanClient:
        return client

    app.dependency_overrides[get_home_assistant_client] = override_client
    app.dependency_overrides[get_action_plan_store] = lambda: store
    app.dependency_overrides[get_settings] = lambda: active_settings
    try:
        yield (
            TestClient(app, headers={"X-API-Key": "plan-api-key"}),
            client,
            store,
            settings,
        )
    finally:
        app.dependency_overrides.pop(get_home_assistant_client, None)
        app.dependency_overrides.pop(get_action_plan_store, None)
        app.dependency_overrides.pop(get_settings, None)
        get_settings.cache_clear()


def _proposal_payload() -> dict[str, object]:
    return {
        "actions": [
            {
                "domain": "light",
                "service": "turn_on",
                "entity_id": ENTITY_ID,
                "data": {"brightness": 100},
                "reason": "Restore the requested lighting level",
            }
        ],
        "expires_in_seconds": 300,
    }


def test_plan_api_previews_then_revalidates_and_executes_once(plan_api) -> None:
    api, client, store, _ = plan_api
    proposed = api.post("/action-plans", json=_proposal_payload())

    assert proposed.status_code == 200
    payload = proposed.json()
    assert payload["status"] == "proposed"
    assert payload["actions"][0]["initial_state"] == "off"
    assert payload["actions"][0]["reason"]
    assert client.calls == []

    approved = api.post(f"/action-plans/{payload['plan_id']}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "executed"
    assert len(client.calls) == 1
    assert store.get(payload["plan_id"]).status == "executed"

    duplicate = api.post(f"/action-plans/{payload['plan_id']}/approve")
    assert duplicate.status_code == 409
    assert len(client.calls) == 1


def test_plan_api_invalidates_changed_starting_state(plan_api) -> None:
    api, client, store, _ = plan_api
    proposed = api.post("/action-plans", json=_proposal_payload()).json()
    client.entity = _entity(state="on")

    approved = api.post(f"/action-plans/{proposed['plan_id']}/approve")

    assert approved.status_code == 409
    assert client.calls == []
    assert store.get(proposed["plan_id"]).status == "invalidated"


def test_plan_api_rechecks_global_kill_switch(plan_api) -> None:
    api, client, store, settings = plan_api
    proposed = api.post("/action-plans", json=_proposal_payload()).json()
    app.dependency_overrides[get_settings] = lambda: settings(False)

    approved = api.post(f"/action-plans/{proposed['plan_id']}/approve")

    assert approved.status_code == 403
    assert client.calls == []
    assert store.get(proposed["plan_id"]).status == "failed"


def test_plan_api_supports_explicit_rejection(plan_api) -> None:
    api, client, store, _ = plan_api
    proposed = api.post("/action-plans", json=_proposal_payload()).json()

    rejected = api.post(f"/action-plans/{proposed['plan_id']}/reject")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.calls == []
    assert store.get(proposed["plan_id"]).status == "rejected"


def test_plan_api_builds_natural_language_request_from_simulation_only(
    plan_api,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api, client, _, _ = plan_api

    async def simulated_agent(*args, **kwargs) -> AgentResponse:
        assert kwargs["action_mode"] == "simulate"
        assert kwargs["persist_conversation"] is False
        return AgentResponse(
            response="Simulated.",
            session_id="plan-example",
            model="example-model",
            iterations=1,
            tools_used=["perform_action"],
            tool_trace=[
                ToolAuditRecord(
                    sequence=1,
                    tool="perform_action",
                    arguments={
                        "domain": "light",
                        "service": "turn_on",
                        "entity_id": ENTITY_ID,
                        "data": {"brightness": 100},
                        "dry_run": True,
                    },
                    status="completed",
                    outcome="simulated",
                )
            ],
        )

    monkeypatch.setattr("house_brain.main.run_agent", simulated_agent)
    proposed = api.post(
        "/action-plans/from-request",
        json={"instruction": "Set the example light", "expires_in_seconds": 300},
    )

    assert proposed.status_code == 200
    assert proposed.json()["status"] == "proposed"
    assert proposed.json()["actions"][0]["entity_id"] == ENTITY_ID
    assert client.calls == []

