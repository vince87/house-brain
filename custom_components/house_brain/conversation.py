"""Conversation entity backed by the House Brain agent API."""

from __future__ import annotations

from typing import Literal, override

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HouseBrainConfigEntry
from .api import HouseBrainApiError
from .const import CONF_CONVERSATION_MODE, DOMAIN
from .entity import HouseBrainEntity
from .models import server_session_id

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HouseBrainConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the House Brain conversation entity."""
    async_add_entities([HouseBrainConversationEntity(config_entry)])


class HouseBrainConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    HouseBrainEntity,
):
    """Expose House Brain as an Assist conversation agent."""

    def __init__(self, entry: HouseBrainConfigEntry) -> None:
        super().__init__(entry, "conversation")
        if entry.data[CONF_CONVERSATION_MODE] == "execute":
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """House Brain accepts every language supported by Home Assistant."""
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        """Register this entity as a conversation agent."""
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Unregister this conversation agent."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Forward one Assist turn to House Brain."""
        session_id = server_session_id(
            self.entry.entry_id,
            user_input.conversation_id,
        )
        try:
            result = await self.entry.runtime_data.client.async_chat(
                user_input.text,
                session_id,
                mode=self.entry.data[CONF_CONVERSATION_MODE],
                language=user_input.language,
            )
        except HouseBrainApiError as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="request_failed",
                translation_placeholders={"error": str(exc)},
            ) from exc

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(
                agent_id=user_input.agent_id,
                content=result.response,
            )
        )
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(result.response)
        return conversation.ConversationResult(
            conversation_id=result.session_id or session_id,
            response=response,
            continue_conversation=chat_log.continue_conversation,
        )
