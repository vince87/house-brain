"""AI Task entity backed by the configured House Brain safety mode."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import override

import voluptuous as vol
from homeassistant.components import ai_task, conversation
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util.json import json_loads
from voluptuous_openapi import convert

from . import HouseBrainConfigEntry
from .api import HouseBrainApiError
from .const import CONF_CONVERSATION_MODE, DOMAIN
from .entity import HouseBrainEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HouseBrainConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the House Brain AI Task entity."""
    async_add_entities([HouseBrainAITaskEntity(config_entry)])


class HouseBrainAITaskEntity(ai_task.AITaskEntity, HouseBrainEntity):
    """Generate data through an audited House Brain event."""

    _attr_supported_features = ai_task.AITaskEntityFeature.GENERATE_DATA

    def __init__(self, entry: HouseBrainConfigEntry) -> None:
        super().__init__(entry, "ai_task")

    @override
    async def _async_generate_data(
        self,
        task: ai_task.GenDataTask,
        chat_log: conversation.ChatLog,
    ) -> ai_task.GenDataTaskResult:
        """Generate plain text or validated structured data."""
        instructions = task.instructions
        if task.structure is not None:
            try:
                schema = convert(task.structure)
            except (TypeError, ValueError, vol.Invalid) as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_structure",
                ) from exc
            instructions = (
                f"{instructions}\n\n"
                "Return only valid JSON matching this schema, without Markdown "
                f"fences or commentary: {json.dumps(schema, ensure_ascii=False)}"
            )

        try:
            result = await self.entry.runtime_data.client.async_ai_task(
                instructions,
                task.name,
                mode=self.entry.data[CONF_CONVERSATION_MODE],
            )
        except HouseBrainApiError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_failed",
                translation_placeholders={"error": str(exc)},
            ) from exc

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=self.entity_id or DOMAIN,
                content=result.response,
            )
        )
        data: object = result.response
        if task.structure is not None:
            try:
                data = task.structure(json_loads(result.response))
            except (JSONDecodeError, vol.Invalid) as exc:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="invalid_structured_response",
                ) from exc

        return ai_task.GenDataTaskResult(
            conversation_id=chat_log.conversation_id,
            data=data,
        )
