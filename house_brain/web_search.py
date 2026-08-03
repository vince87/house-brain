from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, Field

from house_brain.config import Settings


class WebSearchError(Exception):
    """Raised when the configured search service cannot return safe results."""


class WebSearchResult(BaseModel):
    title: str
    url: str
    content: str = ""
    engines: list[str] = Field(default_factory=list)
    published_date: str | None = None


class WebSearchClient:
    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if settings.searxng_url is None:
            raise WebSearchError("Web search is not configured")
        self.url = str(settings.searxng_url).rstrip("/")
        self.max_results = settings.web_search_max_results
        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=settings.web_search_timeout,
            transport=transport,
        )

    async def __aenter__(self) -> "WebSearchClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object,
    ) -> None:
        await self._client.aclose()

    async def search(
        self,
        query: str,
        *,
        limit: int | None = None,
        time_range: str | None = None,
    ) -> list[WebSearchResult]:
        normalized_query = query.strip()
        if not 2 <= len(normalized_query) <= 300:
            raise WebSearchError("Search query must contain 2 to 300 characters")

        bounded_limit = min(max(limit or self.max_results, 1), self.max_results)
        if time_range not in {None, "day", "week", "month", "year"}:
            raise WebSearchError("Invalid search time range")
        params: dict[str, str | int] = {
            "q": normalized_query,
            "format": "json",
            "safesearch": 1,
        }
        if time_range is not None:
            params["time_range"] = time_range
        try:
            response = await self._client.get(
                "/search",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            raw_results = payload["results"]
            if not isinstance(raw_results, list):
                raise TypeError("results is not a list")
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise WebSearchError(
                "SearXNG is unreachable or returned invalid data"
            ) from exc

        results: list[WebSearchResult] = []
        seen_urls: set[str] = set()
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url", "")).strip()
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                continue
            if url in seen_urls:
                continue
            title = str(item.get("title", "")).strip()[:200]
            if not title:
                continue
            raw_engines = item.get("engines", [])
            engines = (
                [str(engine)[:50] for engine in raw_engines[:5]]
                if isinstance(raw_engines, list)
                else []
            )
            results.append(
                WebSearchResult(
                    title=title,
                    url=url,
                    content=str(item.get("content", "")).strip()[:800],
                    engines=engines,
                    published_date=_published_date(item),
                )
            )
            seen_urls.add(url)
            if len(results) >= bounded_limit:
                break
        return results


def _published_date(item: dict[object, object]) -> str | None:
    value = item.get("publishedDate") or item.get("published_date")
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized[:80] or None
