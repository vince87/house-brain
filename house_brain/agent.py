import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from house_brain.actions import ActionBatchRequest, ActionRequest, validate_action
from house_brain.autonomy import AutonomyPolicy, AutonomyPolicyError
from house_brain.config import Settings
from house_brain.conversations import ConversationStore
from house_brain.events import EventMode
from house_brain.home_assistant import HomeAssistantClient
from house_brain.memory import MemoryInput, MemoryStore
from house_brain.ollama import OllamaClient, OllamaError

MAX_AGENT_ITERATIONS = 6

SYSTEM_PROMPT = """Sei House Brain, assistente domestico di Vincenzo.
Rispondi sempre in italiano, in modo diretto e breve.
Usa i tool per leggere dati reali: non inventare stati della casa.
Se non conosci l'entity_id esatto, usa search_entities prima degli altri tool.
Non confondere automation e script con i dispositivi controllati: lo stato on di
un'automazione significa abilitata, non che il dispositivo sia acceso.
Quando la domanda riguarda profilo, preferenze o decisioni precedenti, usa
recall_memories prima di rispondere.
Per i comandi, usa dry_run=true se Vincenzo non chiede esplicitamente di
eseguire davvero. Le policy del server sono inderogabili.
Se un tool restituisce un errore correggibile, correggi gli argomenti e riprova.
Non fingere mai che un comando abbia funzionato.
Salva ricordi solo se Vincenzo chiede esplicitamente di ricordare o dichiara
una preferenza stabile. Dimentica solo su richiesta esplicita; il ricordo finirà
nel cestino recuperabile.
Negli eventi automatici il trigger è contesto, non un'azione già decisa:
individua i dispositivi pertinenti, recupera le preferenze stabili necessarie e
leggi gli stati correnti prima di pianificare. Per più dispositivi usa
list_entities e perform_actions. Non comandare domini non consentiti anche se
sono visibili in Home Assistant.
Per le cover, effective_state e current_position sono autoritativi rispetto a
state: posizione 0 significa chiusa, 100 aperta e un valore intermedio
parzialmente aperta.
Se concludi che serve una o più azioni, devi chiamare perform_action o
perform_actions prima della risposta finale, anche in modalità simulate. Non
scrivere che procederai, eseguirai o sistemerai qualcosa senza il risultato del
tool. Se non serve agire, dichiaralo esplicitamente.
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
            "name": "list_entities",
            "description": (
                "Legge in un'unica istantanea gli stati compatti delle entità "
                "appartenenti ai domini richiesti. Utile per ragionare su più "
                "tapparelle, luci, sensori, telecamere o altri dispositivi."
            ),
            "parameters": {
                "type": "object",
                "required": ["domains"],
                "properties": {
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "maxItems": 8,
                    },
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 50,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "perform_actions",
            "description": (
                "Simula o esegue un piano da 1 a 20 azioni. L'intero piano "
                "viene validato prima di inviare qualunque comando."
            ),
            "parameters": {
                "type": "object",
                "required": ["actions"],
                "properties": {
                    "actions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "required": ["domain", "service", "entity_id"],
                            "properties": {
                                "domain": {
                                    "type": "string",
                                    "enum": [
                                        "light",
                                        "switch",
                                        "cover",
                                        "climate",
                                    ],
                                },
                                "service": {"type": "string"},
                                "entity_id": {"type": "string"},
                                "data": {"type": "object", "default": {}},
                                "dry_run": {
                                    "type": "boolean",
                                    "default": True,
                                },
                            },
                        },
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
    {
        "type": "function",
        "function": {
            "name": "search_entities",
            "description": "Trova entity_id reali da nome, stanza o descrizione.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string"},
                    "domain": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 20,
                        "default": 10,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memories",
            "description": "Cerca fatti e preferenze persistenti di Vincenzo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 10,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember_fact",
            "description": "Salva un fatto esplicitamente richiesto come memoria.",
            "parameters": {
                "type": "object",
                "required": ["key", "value"],
                "properties": {
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "category": {"type": "string", "default": "fact"},
                    "importance": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget_memory",
            "description": "Sposta nel cestino un ricordo su richiesta esplicita.",
            "parameters": {
                "type": "object",
                "required": ["key"],
                "properties": {"key": {"type": "string"}},
            },
        },
    },
]


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=4000)
    session_id: str = Field(
        default="default",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )


class AgentResponse(BaseModel):
    response: str
    session_id: str
    model: str
    iterations: int
    tools_used: list[str]


async def run_agent(
    request: AgentRequest,
    settings: Settings,
    home_assistant: HomeAssistantClient,
    memory_store: MemoryStore,
    conversation_store: ConversationStore,
    *,
    action_mode: EventMode | None = None,
    autonomy_policy: AutonomyPolicy | None = None,
    persist_conversation: bool = True,
) -> AgentResponse:
    history = (
        await asyncio.to_thread(
            conversation_store.history,
            request.session_id,
            limit=12,
        )
        if persist_conversation
        else []
    )
    prompt = SYSTEM_PROMPT + _event_mode_instruction(action_mode)
    messages: list[dict[str, object]] = [
        {"role": "system", "content": prompt},
        *[
            {"role": item.role, "content": item.content}
            for item in history
        ],
        {"role": "user", "content": request.message},
    ]
    tools_used: list[str] = []

    async with OllamaClient(settings) as ollama:
        for iteration in range(1, MAX_AGENT_ITERATIONS + 1):
            assistant = await ollama.chat(messages, TOOLS)
            messages.append(assistant)
            calls = assistant.get("tool_calls") or []

            if not calls:
                content = assistant.get("content")
                if not isinstance(content, str) or not content.strip():
                    raise OllamaError("Ollama returned an empty response")
                response = content.strip()
                await asyncio.to_thread(
                    conversation_store.add_exchange,
                    request.session_id,
                    request.message,
                    response,
                ) if persist_conversation else None
                return AgentResponse(
                    response=response,
                    session_id=request.session_id,
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
                        memory_store,
                        action_mode=action_mode,
                        autonomy_policy=autonomy_policy,
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

    raise OllamaError(
        f"Agent stopped after {MAX_AGENT_ITERATIONS} iterations"
    )


def _event_mode_instruction(mode: EventMode | None) -> str:
    if mode is None:
        return ""
    instructions = {
        "observe": (
            "\nModalità evento OBSERVE imposta dal server: analizza e rispondi, "
            "ma non richiedere azioni."
        ),
        "simulate": (
            "\nModalità evento SIMULATE imposta dal server: puoi proporre azioni, "
            "che saranno soltanto simulate."
        ),
        "execute": (
            "\nModalità evento EXECUTE imposta dal server: richiedi soltanto "
            "azioni necessarie e consentite. Le azioni autorizzate saranno reali."
        ),
    }
    return instructions[mode]


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
    memory_store: MemoryStore,
    *,
    action_mode: EventMode | None = None,
    autonomy_policy: AutonomyPolicy | None = None,
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

    if name == "list_entities":
        raw_domains = arguments.get("domains")
        if not isinstance(raw_domains, list):
            raise ValueError("domains must be a list")
        domains = {str(domain).strip().lower() for domain in raw_domains}
        if not 1 <= len(domains) <= 8 or any(
            not domain or "." in domain for domain in domains
        ):
            raise ValueError("domains must contain 1 to 8 valid domains")
        limit = min(max(int(arguments.get("limit", 50)), 1), 100)
        return await client.list_entities(domains=domains, limit=limit)

    if name == "perform_action":
        action = ActionRequest.model_validate(arguments)
        results = await _execute_action_plan(
            [action],
            client,
            action_mode=action_mode,
            autonomy_policy=autonomy_policy,
        )
        return results[0]

    if name == "perform_actions":
        plan = ActionBatchRequest.model_validate(arguments)
        results = await _execute_action_plan(
            plan.actions,
            client,
            action_mode=action_mode,
            autonomy_policy=autonomy_policy,
        )
        return {
            "status": (
                "blocked_by_event_mode"
                if action_mode == "observe"
                else "completed"
            ),
            "actions": results,
        }

    if name == "search_entities":
        limit = min(max(int(arguments.get("limit", 10)), 1), 20)
        domain = arguments.get("domain")
        return await client.search_entities(
            str(arguments["query"]),
            domain=str(domain) if domain else None,
            limit=limit,
        )

    if name == "recall_memories":
        query = arguments.get("query")
        limit = int(arguments.get("limit", 10))
        memories = await asyncio.to_thread(
            memory_store.search,
            str(query) if query else None,
            limit=min(max(limit, 1), 10),
        )
        return [item.model_dump(mode="json") for item in memories]

    if name == "remember_fact":
        memory = MemoryInput.model_validate(arguments)
        saved = await asyncio.to_thread(memory_store.remember, memory)
        return {"status": "remembered", "memory": saved.model_dump(mode="json")}

    if name == "forget_memory":
        key = str(arguments["key"])
        forgotten = await asyncio.to_thread(memory_store.forget, key)
        return {
            "status": "moved_to_trash" if forgotten else "not_found",
            "key": key,
        }

    raise ValueError(f"Unknown tool: {name}")



async def _execute_action_plan(
    actions: list[ActionRequest],
    client: HomeAssistantClient,
    *,
    action_mode: EventMode | None,
    autonomy_policy: AutonomyPolicy | None,
) -> list[dict[str, Any]]:
    """Validate the complete plan before performing its first side effect."""
    for action in actions:
        validate_action(action)
        if action_mode is not None and action_mode != "observe":
            if autonomy_policy is None:
                raise AutonomyPolicyError(
                    "Autonomous actions require an explicit allowlist"
                )
            autonomy_policy.validate_action(action)

    if action_mode == "observe":
        return [
            {
                "status": "blocked_by_event_mode",
                "mode": action_mode,
                "action": action.model_dump(),
            }
            for action in actions
        ]

    normalized = actions
    if action_mode == "simulate":
        normalized = [
            action.model_copy(update={"dry_run": True})
            for action in actions
        ]
    elif action_mode == "execute":
        normalized = [
            action.model_copy(update={"dry_run": False})
            for action in actions
        ]

    results: list[dict[str, Any]] = []
    for action in normalized:
        if action.dry_run:
            results.append({"status": "simulated", **action.model_dump()})
            continue
        response = await client.call_service(
            action.domain,
            action.service,
            entity_id=action.entity_id,
            data=action.data,
        )
        results.append(
            {
                "status": "executed",
                "domain": action.domain,
                "service": action.service,
                "entity_id": action.entity_id,
                "data": action.data,
                "response": response,
            }
        )
    return results
