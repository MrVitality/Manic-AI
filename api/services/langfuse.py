"""Langfuse tracing integration."""

import logging

from api.config import settings

logger = logging.getLogger(__name__)

_langfuse_client = None


def _set_langfuse(client):
    import api.services.langfuse as _mod
    _mod._langfuse_client = client


def init_langfuse(*, app=None):
    try:
        from langfuse import Langfuse
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            client = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST,
            )
            _set_langfuse(client)
            logger.info("Langfuse tracing enabled")
            if app is not None:
                app.state.langfuse = client
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Langfuse init failed: %s", e)


def get_langfuse():
    return _langfuse_client
