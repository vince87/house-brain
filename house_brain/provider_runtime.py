"""Safe provider capabilities and aggregate runtime measurements."""

from dataclasses import dataclass
from threading import Lock
from typing import Literal

from pydantic import BaseModel

ToolSupport = Literal["supported", "unsupported", "unknown"]


class ModelCapabilities(BaseModel):
    """Capabilities explicitly reported by the configured model provider."""

    provider: str
    model: str
    tool_support: ToolSupport
    source: str
    response_only_available: bool = True


@dataclass
class _ProviderCounters:
    requests: int = 0
    successes: int = 0
    failures: int = 0
    retries: int = 0
    recoveries: int = 0
    total_latency_ms: float = 0.0
    last_latency_ms: float | None = None


class ProviderMetrics:
    """Keep process-local counters without prompts, responses, or credentials."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._providers: dict[str, _ProviderCounters] = {}

    def record_success(self, provider: str, latency_seconds: float) -> None:
        self._record_request(provider, latency_seconds, succeeded=True)

    def record_failure(self, provider: str, latency_seconds: float) -> None:
        self._record_request(provider, latency_seconds, succeeded=False)

    def _record_request(
        self,
        provider: str,
        latency_seconds: float,
        *,
        succeeded: bool,
    ) -> None:
        latency_ms = max(0.0, latency_seconds * 1000)
        with self._lock:
            counters = self._providers.setdefault(provider, _ProviderCounters())
            counters.requests += 1
            if succeeded:
                counters.successes += 1
            else:
                counters.failures += 1
            counters.total_latency_ms += latency_ms
            counters.last_latency_ms = latency_ms

    def record_retry(self, provider: str) -> None:
        with self._lock:
            self._providers.setdefault(provider, _ProviderCounters()).retries += 1

    def record_recovery(self, provider: str) -> None:
        with self._lock:
            self._providers.setdefault(provider, _ProviderCounters()).recoveries += 1

    def snapshot(self) -> dict[str, dict[str, int | float | None]]:
        with self._lock:
            return {
                provider: {
                    "requests": counters.requests,
                    "successes": counters.successes,
                    "failures": counters.failures,
                    "retries": counters.retries,
                    "recoveries": counters.recoveries,
                    "average_latency_ms": round(
                        counters.total_latency_ms / counters.requests,
                        2,
                    )
                    if counters.requests
                    else None,
                    "last_latency_ms": round(counters.last_latency_ms, 2)
                    if counters.last_latency_ms is not None
                    else None,
                }
                for provider, counters in sorted(self._providers.items())
            }

    def reset(self) -> None:
        """Clear counters for deterministic tests."""
        with self._lock:
            self._providers.clear()


provider_metrics = ProviderMetrics()
