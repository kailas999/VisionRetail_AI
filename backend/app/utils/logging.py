"""Structured JSON logging with per-request trace IDs."""
import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

# Context variable — set per request by middleware
request_trace_id: ContextVar[str] = ContextVar(
    "request_trace_id", default="no-trace"
)


class JSONFormatter(logging.Formatter):
    """Emit structured JSON log lines compatible with cloud log aggregators."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": request_trace_id.get("no-trace"),
        }
        if record.exc_info:
            log_dict["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            log_dict.update(record.extra)
        return json.dumps(log_dict, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def new_trace_id() -> str:
    return str(uuid.uuid4())
