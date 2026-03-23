"""Centralized JSON logging configuration with request ID correlation."""
import logging
import logging.config
import contextvars
from pythonjsonlogger import jsonlogger

# ContextVar to hold the current request ID
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('request_id', default='-')


class RequestIdFilter(logging.Filter):
    """Injects request_id from contextvars into every log record."""

    def filter(self, record):
        record.request_id = request_id_var.get('-')
        return True


def setup_logging(log_level: str = "INFO"):
    """Configure JSON structured logging for the entire application."""
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "request_id": {
                "()": RequestIdFilter,
            }
        },
        "formatters": {
            "json": {
                "()": jsonlogger.JsonFormatter,
                "format": "%(asctime)s %(name)s %(levelname)s %(message)s %(request_id)s",
                "rename_fields": {"asctime": "timestamp", "levelname": "level", "name": "logger"},
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "filters": ["request_id"],
                "stream": "ext://sys.stdout",
            }
        },
        "root": {
            "level": log_level,
            "handlers": ["console"],
        },
        "loggers": {
            "uvicorn": {"level": log_level, "handlers": ["console"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
    }
    logging.config.dictConfig(config)
