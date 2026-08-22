import logging
from collections import deque
from datetime import datetime
from threading import Lock
from typing import Any

from loguru import logger
from pydantic import BaseModel

from house_brain.config import Settings

MAX_RUNTIME_LOGS = 1000
STANDARD_LOGGER_NAMES = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "httpx",
    "httpcore",
)


class RuntimeLogRecord(BaseModel):
    sequence: int
    timestamp: datetime
    level: str
    module: str
    function: str
    message: str


class RuntimeLogBuffer:
    def __init__(self, capacity: int = MAX_RUNTIME_LOGS) -> None:
        self._records: deque[RuntimeLogRecord] = deque(maxlen=capacity)
        self._lock = Lock()
        self._sequence = 0

    def write(self, message: Any) -> None:
        record = message.record
        module = str(record.get("name") or "")
        if not module.startswith("house_brain"):
            return
        with self._lock:
            self._sequence += 1
            self._records.append(
                RuntimeLogRecord(
                    sequence=self._sequence,
                    timestamp=record["time"],
                    level=record["level"].name,
                    module=module,
                    function=str(record.get("function") or ""),
                    message=str(record.get("message") or ""),
                )
            )

    def write_standard(self, record: logging.LogRecord) -> None:
        if not record.name.startswith(("uvicorn", "httpx", "httpcore")):
            return
        with self._lock:
            self._sequence += 1
            self._records.append(
                RuntimeLogRecord(
                    sequence=self._sequence,
                    timestamp=datetime.fromtimestamp(record.created).astimezone(),
                    level=record.levelname,
                    module=record.name,
                    function=record.funcName,
                    message=record.getMessage(),
                )
            )

    def list(
        self,
        settings: Settings,
        *,
        limit: int,
        level: str | None = None,
        query: str | None = None,
    ) -> list[RuntimeLogRecord]:
        with self._lock:
            records = list(self._records)
        if level:
            records = [item for item in records if item.level == level]
        if query:
            needle = query.casefold()
            records = [
                item
                for item in records
                if needle in item.message.casefold()
                or needle in item.module.casefold()
            ]
        secrets = _runtime_secrets(settings)
        return [
            item.model_copy(
                update={"message": _redact_message(item.message, secrets)}
            )
            for item in records[-limit:]
        ]


def install_runtime_log_sink(buffer: RuntimeLogBuffer) -> int:
    return logger.add(buffer.write, level="INFO", enqueue=False, catch=True)


class RuntimeStandardLogHandler(logging.Handler):
    def __init__(self, buffer: RuntimeLogBuffer) -> None:
        super().__init__(level=logging.INFO)
        self.buffer = buffer

    def emit(self, record: logging.LogRecord) -> None:
        if getattr(record, "_house_brain_runtime_captured", False):
            return
        try:
            record._house_brain_runtime_captured = True
            self.buffer.write_standard(record)
        except Exception:
            self.handleError(record)


def install_standard_log_sink(
    buffer: RuntimeLogBuffer,
) -> tuple[RuntimeStandardLogHandler, tuple[logging.Logger, ...]]:
    handler = RuntimeStandardLogHandler(buffer)
    attached: list[logging.Logger] = []
    for name in STANDARD_LOGGER_NAMES:
        target = logging.getLogger(name)
        if handler not in target.handlers:
            target.addHandler(handler)
            attached.append(target)
    return handler, tuple(attached)


def remove_standard_log_sink(
    handler: RuntimeStandardLogHandler,
    attached: tuple[logging.Logger, ...],
) -> None:
    for target in attached:
        target.removeHandler(handler)


def _runtime_secrets(settings: Settings) -> tuple[str, ...]:
    candidates = [
        settings.home_assistant_token.get_secret_value(),
        settings.api_key.get_secret_value() if settings.api_key else "",
        (
            settings.openai_api_key.get_secret_value()
            if settings.openai_api_key
            else ""
        ),
        *(
            code.get_secret_value()
            if hasattr(code, "get_secret_value")
            else str(code)
            for code in settings.autonomy_policy.entity_codes.values()
        ),
    ]
    return tuple(value for value in candidates if value)


def _redact_message(message: str, secrets: tuple[str, ...]) -> str:
    redacted = message
    for secret in secrets:
        redacted = redacted.replace(secret, "[redacted]")
    return redacted


runtime_log_buffer = RuntimeLogBuffer()
