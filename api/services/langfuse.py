import logging

from api.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

logger = logging.getLogger(__name__)

langfuse_client = None


def init_langfuse():
    global langfuse_client
    try:
        from langfuse import Langfuse
        if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
            langfuse_client = Langfuse(
                public_key=LANGFUSE_PUBLIC_KEY,
                secret_key=LANGFUSE_SECRET_KEY,
                host=LANGFUSE_HOST,
            )
            logger.info("Langfuse tracing enabled")
    except ImportError:
        pass
    except Exception as e:
        logger.warning("Langfuse init failed: %s", e)


def get_langfuse():
    return langfuse_client
