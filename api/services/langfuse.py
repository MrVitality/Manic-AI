from api.config import LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST

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
            print("Langfuse tracing enabled")
    except ImportError:
        pass
    except Exception as e:
        print(f"[WARN] Langfuse init failed: {e}")


def get_langfuse():
    return langfuse_client
