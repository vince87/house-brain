import json
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from house_brain.actions import ActionRequest, validate_action
from house_brain.config import Settings
from house_brain.home_assistant import HomeAssistantClient
from house_brain.ollama import OllamaClient, OllamaError

SYSTEM_PROMPT = """Sei House Brain, assistente domestico di Vincenzo.
Rispondi sempre in italiano, in modo diretto e breve.
Usa i tool per leggere dati reali: non inventare stati della casa.
Per i comandi, usa dry_run=true se Vincenzo non chiede esplicitamente di
eseguire davvero. Le policy del server sono inderogabili.
Se un tool restituisce un errore correggibile, correggi gli argomenti e riprova.
Non fingere mai che un comando abbia funzionato.
Sei dentro un agent loop e puoi usare più tool prima della risposta finale."""


TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_entity",
            "description": "Legge lo stato corrente di un'entità Home Assistant.",
            "parameters": {
                "type": "object",
                "required": ["entity_id"],
                "properties": {"entity_id": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_history",
            "description": "Legge la cronologia recente di un'entità.",
            "parameters": {
                "type": "object",
                "required": ["entity_id"],
                "properties": {
                    "entity_id": {"type": "string"},
                    "minutes": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10080,
                        "default": 60,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "perform_action",
            "description": (
                "Simula o esegue un comando. Servizi esatti: cover usa "
                "open_cover, close_cover, stop_cover, set_cover_position; "
                "light e switch usano turn_on, turn_off, toggle; climate usa "
                "turn_on, turn_off, set_temperature, set_hvac_mode."
            ),
            "parameters": {
                "type": "object",
                "required": ["domain", "service", "entity_id"],
                "properties": {
                    "domain": {
                        "type": "string",
                        "enum": ["light", "switch", "cover", "climate"],
                    },
                    "service": {
                        "type": "string",
                        "enum": [
                            "turn_on",
                            "turn_off",
                            "toggle",
                            "open_cover",
                            "close_cover",
                            "stop_cover",
                            "set_cover_position",
                            "set_temperature",
                            "set_hvac_mode",
                        ],
                    },
                    "entity_id": {"type": "string"},
                    "data": {"type": "object", "default": {}},
                    "dry_run": {"type": "boolean", "default": True},
                },
            },
        },
    },
]


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)


class AgentResponse(BaseModel):
    response: str
    model: str
    iterations: int
    tools_used: list[str]


async def run_agent(
    request: AgentRequest,
    settings: Settings,
    home_assistant: HomeAssistantClient,
) -> AgentResponse:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": request.message},
    ]
    tools_used: list[str] = []

    async with OllamaClient(settings) as ollama:
        for iteration in range(1, 5):
            assistant = await ollama.chat(messages, TOOLS)
            messages.append(assistant)
            calls = assistant.get("tool_calls") or []

            if not calls:
                content = assistant.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise OllamaError("Ollama returned an empty response")
                return AgentResponse(
                    response=content.strip(),
                    model=settings.ollama_model,
                    iterations=iteration,
                    tools_used=tools_used,
                )

            if not isinstance(calls, list):
                raise OllamaError("Ollama returned invalid tool calls")

            for call in calls:
                name, arguments = _parse_tool_call(call)
                tools_used.append(name)
                tool_log = logger.bind(
                    tool=name,
                    argument_keys=sorted(arguments),
                )
                tool_log.info(
                    "Agent tool requested: tool={} argument_keys={}",
                    name,
                    sorted(arguments),
                )
                try:
                    result = await _execute_tool(
                        name,
                        arguments,
                        home_assistant,
                    )
                    outcome = (
                        result.get("status", "completed")
                        if isinstance(result, dict)
                        else "completed"
                    )
                    tool_log.info(
                        "Agent tool completed: tool={} outcome={}",
                        name,
                        outcome,
                    )
                except Exception as exc:
                    tool_log.warning(
                        "Agent tool failed: tool={} error={}",
                        name,
                        exc,
                    )
                    result = {"error": str(exc)}

                messages.append(
                    {
                        "role": "tool",
                        "tool_name": name,
                        "content": json.dumps(
                            result,
                            ensure_ascii=False,
                            default=str,
                        ),
                    }
                )

    raise OllamaError("Agent stopped after 4 iterations")


def _parse_tool_call(call: object) -> tuple[str, dict[str, Any]]:
    if not isinstance(call, dict):
        raise OllamaError("Invalid tool call")
    function = call.get("function")
    if not isinstance(function, dict):
        raise OllamaError("Invalid tool function")
    name = function.get("name")
    arguments = function.get("arguments", {})
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise OllamaError("Invalid tool arguments")
    return name, arguments


async def _execute_tool(
    name: str,
    arguments: dict[str, Any],
    client: HomeAssistantClient,
) -> object:
    if name == "get_entity":
        return (
            await client.get_entity(str(arguments["entity_id"]))
        ).model_dump(mode="json")

    if name == "get_history":
        minutes = int(arguments.get("minutes", 60))
        if not 1 <= minutes <= 10_080:
            raise ValueError("minutes must be between 1 and 10080")
        end = datetime.now(UTC)
        history = await client.get_history(
            str(arguments["entity_id"]),
            start=end - timedelta(minutes=minutes),
            end=end,
        )
        return [item.model_dump(mode="json") for item in history]

    if name == "perform_action":
        action = ActionRequest.model_validate(arguments)
        validate_action(action)
        if action.dry_run:
            return {"status": "simulated", **action.model_dump()}
        response = await client.call_service(
            action.domain,
            action.service,
            entity_id=action.entity_id,
            data=action.data,
        )
        return {"status": "executed", "response": response}

    raise ValueError(f"Unknown tool: {name}")
