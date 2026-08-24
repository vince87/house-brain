from pathlib import Path

import pytest

from house_brain.context_views import (
    ContextViewCatalog,
    ContextViewError,
    dump_context_views,
    load_context_views,
    parse_context_views,
    save_context_views,
)


VALID = """
version: 1
default_view: example_daytime
views:
  - id: example_daytime
    name: Example daytime
    enabled: true
    areas:
      - example_ground_floor
    domains:
      - light
      - cover
    entities:
      - sensor.example_temperature
    max_entities: 40
    include_linked_memories: true
"""


def test_parse_context_views_accepts_generic_policy_narrowing_view() -> None:
    catalog = parse_context_views(VALID)

    view = catalog.get("example_daytime")
    assert catalog.default_view == "example_daytime"
    assert view.name == "Example daytime"
    assert view.areas == ("example_ground_floor",)
    assert view.domains == ("light", "cover")
    assert view.entities == ("sensor.example_temperature",)
    assert view.max_entities == 40
    assert view.include_linked_memories is True


def test_missing_context_view_file_preserves_existing_behaviour(tmp_path: Path) -> None:
    catalog = load_context_views(tmp_path / "context-views.yaml")

    assert catalog == ContextViewCatalog.empty()
    assert catalog.enabled_views() == ()


@pytest.mark.parametrize(
    "content",
    [
        "version: 2\nviews: []\n",
        "version: 1\nunexpected: true\nviews: []\n",
        "version: 1\ndefault_view: missing\nviews: []\n",
        (
            "version: 1\nviews:\n"
            "  - id: duplicate\n    name: First\n    domains: [light]\n"
            "  - id: duplicate\n    name: Second\n    domains: [cover]\n"
        ),
        (
            "version: 1\nviews:\n"
            "  - id: empty\n    name: Empty\n"
        ),
        (
            "version: 1\nviews:\n"
            "  - id: invalid\n    name: Invalid\n"
            "    entities: [not-an-entity]\n"
        ),
        (
            "version: 1\nviews:\n"
            "  - id: invalid\n    name: Invalid\n"
            "    domains: [light.example]\n"
        ),
        "version: 1\nversion: 1\nviews: []\n",
    ],
)
def test_context_views_reject_invalid_or_ambiguous_configuration(
    content: str,
) -> None:
    with pytest.raises(ContextViewError):
        parse_context_views(content)


def test_disabled_context_view_is_not_runtime_selectable() -> None:
    catalog = parse_context_views(
        """
version: 1
views:
  - id: disabled_example
    name: Disabled example
    enabled: false
    domains: [light]
"""
    )

    assert catalog.enabled_views() == ()
    with pytest.raises(ContextViewError, match="Unknown or disabled"):
        catalog.get("disabled_example")
    assert catalog.get("disabled_example", include_disabled=True).enabled is False


def test_context_views_round_trip_and_save_atomically(tmp_path: Path) -> None:
    catalog = parse_context_views(VALID)
    target = tmp_path / "config" / "context-views.yaml"

    save_context_views(target, catalog)

    assert load_context_views(target) == catalog
    assert parse_context_views(dump_context_views(catalog)) == catalog
    assert list(target.parent.glob(".*.tmp")) == []


def test_context_view_ids_and_selectors_are_normalized() -> None:
    catalog = parse_context_views(
        """
version: 1
default_view: EXAMPLE_VIEW
views:
  - id: EXAMPLE_VIEW
    name: "  Example   view  "
    areas: [" Example Room "]
    domains: [" LIGHT "]
    entities: [" SENSOR.EXAMPLE_TEMPERATURE "]
"""
    )

    view = catalog.get("example_view")
    assert catalog.default_view == "example_view"
    assert view.name == "Example view"
    assert view.areas == ("Example Room",)
    assert view.domains == ("light",)
    assert view.entities == ("sensor.example_temperature",)
