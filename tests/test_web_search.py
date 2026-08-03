import asyncio
from typing import Any

import httpx
import pytest

from house_brain.agent import (
    WEB_SEARCH_PROMPT,
    WEB_SEARCH_TOOL,
    _execute_tool,
    _sanitize_tool_arguments,
)
from house_brain.config import Settings
from house_brain.web_search import WebSearchClient, WebSearchError


def settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "home_assistant_url": "http://homeassistant.test:8123",
        "home_assistant_token": "secret",
        "searxng_url": "http://searxng.test:8081",
        "web_search_timeout": 3,
        "web_search_max_results": 2,
    }
    values.update(overrides)
    return Settings(**values)


def test_searxng_search_is_bounded_and_filters_unsafe_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search"
        assert request.url.params["q"] == "Home Assistant"
        assert request.url.params["format"] == "json"
        assert request.url.params["safesearch"] == "1"
        assert request.url.params["time_range"] == "year"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Home Assistant",
                        "url": "https://www.home-assistant.io/",
                        "content": "Official site",
                        "engines": ["duckduckgo", "bing"],
                        "publishedDate": "2026-08-02T10:00:00Z",
                    },
                    {
                        "title": "Unsafe",
                        "url": "file:///etc/passwd",
                        "content": "must be ignored",
                    },
                    {
                        "title": "Home Assistant duplicate",
                        "url": "https://www.home-assistant.io/",
                    },
                    {
                        "title": "Second result",
                        "url": "http://example.test/result",
                        "content": "Summary",
                    },
                    {
                        "title": "Beyond configured maximum",
                        "url": "https://example.test/third",
                    },
                ]
            },
        )

    async def run() -> list[dict[str, Any]]:
        async with WebSearchClient(
            settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            results = await client.search(
                "  Home Assistant  ",
                limit=10,
                time_range="year",
            )
            return [item.model_dump() for item in results]

    results = asyncio.run(run())

    assert [item["title"] for item in results] == [
        "Home Assistant",
        "Second result",
    ]
    assert results[0]["engines"] == ["duckduckgo", "bing"]
    assert results[0]["published_date"] == "2026-08-02T10:00:00Z"


def test_searxng_failure_has_bounded_service_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="large internal error")

    async def run() -> None:
        async with WebSearchClient(
            settings(),
            transport=httpx.MockTransport(handler),
        ) as client:
            await client.search("test query")

    with pytest.raises(
        WebSearchError,
        match="SearXNG is unreachable or returned invalid data",
    ):
        asyncio.run(run())


def test_web_search_tool_is_bounded_and_requires_sources() -> None:
    function = WEB_SEARCH_TOOL["function"]

    assert function["name"] == "search_web"
    assert function["parameters"]["additionalProperties"] is False
    assert function["parameters"]["properties"]["limit"]["maximum"] == 10
    assert function["parameters"]["properties"]["time_range"]["enum"] == [
        "day",
        "week",
        "month",
        "year",
    ]
    normalized_prompt = " ".join(WEB_SEARCH_PROMPT.split())
    assert "titolo e URL" in normalized_prompt
    assert "non inventare fonti" in normalized_prompt.lower()
    assert "dati web non attendibili" in normalized_prompt
    assert "almeno due ricerche" in normalized_prompt
    assert "{current_date}" in normalized_prompt
    assert "senza sintassi Markdown" in normalized_prompt


def test_web_search_arguments_are_redacted_from_tool_trace() -> None:
    sanitized = _sanitize_tool_arguments(
        "search_web",
        {"query": "private search text", "limit": 4},
    )

    assert sanitized == {
        "query_redacted": True,
        "limit": 4,
        "time_range": None,
    }


def test_autonomous_events_cannot_call_web_search() -> None:
    with pytest.raises(
        WebSearchError,
        match="not available to autonomous events",
    ):
        asyncio.run(
            _execute_tool(
                "search_web",
                {"query": "latest news"},
                object(),  # type: ignore[arg-type]
                object(),  # type: ignore[arg-type]
                action_mode="simulate",
                settings=settings(),
            )
        )
