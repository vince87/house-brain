from house_brain.languages import (
    SUPPORTED_LANGUAGES,
    localized_message,
    localized_rejection,
    localized_ui_messages,
    response_language_instruction,
)


def test_ten_language_packs_are_installed() -> None:
    assert SUPPORTED_LANGUAGES == (
        "ar",
        "de",
        "en",
        "es",
        "fr",
        "it",
        "ja",
        "ko",
        "pt",
        "zh",
    )


def test_regional_tag_uses_primary_language_pack() -> None:
    assert "nessuna azione" in localized_message(
        "authorization_invalid",
        "it-IT",
    )
    assert "nenhuma ação" in localized_message(
        "authorization_invalid",
        "pt-BR",
    )


def test_action_rejections_use_configured_language() -> None:
    assert localized_rejection("not_included", "en").startswith("The plan was rejected")
    assert localized_rejection("not_included", "es").startswith("El plan fue rechazado")


def test_model_instruction_requires_translation_and_preserves_ids() -> None:
    instruction = response_language_instruction("fr")

    assert "MANDATORY OUTPUT LANGUAGE" in instruction
    assert "'fr'" in instruction
    assert "Never translate Home Assistant entity IDs" in instruction


def test_action_audit_labels_exist_in_every_ui_language() -> None:
    required = {
        "audit_reason",
        "audit_simulated",
        "audit_executed",
        "audit_rejected",
        "audit_completed",
    }

    for language in SUPPORTED_LANGUAGES:
        assert required <= localized_ui_messages(language).keys()
