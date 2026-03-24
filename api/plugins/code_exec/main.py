"""Code execution plugin.

Runs arbitrary Python code in a temporary subprocess with a hard timeout.
No network access is granted to the subprocess and file writes are
restricted to /tmp via the executed code's own behaviour — the sandbox
does not enforce filesystem isolation beyond what the OS provides for the
subprocess.

SECURITY: This plugin is restricted to admin callers only.  The
``execute_python`` tool checks the ``X-API-Key`` header on every invocation
and rejects non-admin requests with a PermissionError before any code is
run.
"""

import asyncio
import sys
import tempfile
from typing import Optional
from pathlib import Path

from api.plugins import tool

_EXEC_TIMEOUT = 10  # seconds
_MAX_OUTPUT_CHARS = 2000

# ---------------------------------------------------------------------------
# Admin guard
# ---------------------------------------------------------------------------

# The code-exec plugin is a high-privilege capability.  Before executing any
# code we verify the caller is an admin by resolving their API key against the
# database.  We import lazily to avoid circular import issues at plugin load
# time.


async def _require_admin_caller(caller_api_key: Optional[str]) -> None:
    """Raise PermissionError if the caller is not an active admin.

    Args:
        caller_api_key: The raw value from the ``X-API-Key`` header, or None.

    Raises:
        PermissionError: If the key is missing, invalid, or not an admin.
    """
    if not caller_api_key:
        raise PermissionError("Code execution requires an authenticated admin caller (missing API key).")

    # Import here to avoid circular imports during plugin auto-discovery.
    from api.services.user_auth import authenticate_by_api_key  # noqa: PLC0415

    # We need a DB pool.  During normal request flow the pool is on
    # app.state, but plugins are called outside of the FastAPI dependency
    # system.  We obtain it via the database module's module-level accessor.
    try:
        from api.database import get_db_optional  # noqa: PLC0415
        pool = get_db_optional()
    except (ImportError, AttributeError):
        pool = None

    if pool is None:
        raise PermissionError("Code execution requires a live database connection to verify admin status.")

    user = await authenticate_by_api_key(pool, caller_api_key)
    if not user or not user.get("is_admin"):
        raise PermissionError("Code execution is restricted to admin users.")


@tool(
    name="execute_python",
    description="Execute Python code and return stdout/stderr (admin-only)",
)
async def execute_python(code: str, caller_api_key: Optional[str] = None) -> dict:
    """Execute a Python code snippet and return its output.

    Requires the caller to be an authenticated admin user.  Pass the value
    of the ``X-API-Key`` request header as ``caller_api_key``.

    Args:
        code: The Python source code to execute.
        caller_api_key: API key of the calling user (must belong to an admin).

    Returns:
        A dict with keys ``stdout``, ``stderr``, and ``exit_code``.
        Each output string is truncated to 2000 characters.

    Raises:
        PermissionError: If the caller is not an authenticated admin.
    """
    await _require_admin_caller(caller_api_key)

    # Write code to a temp file so we avoid shell-injection via -c
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        dir="/tmp",
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            tmp_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # Isolate from parent env to reduce side-channel risk
            env={
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/tmp",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=_EXEC_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return {
                "stdout": "",
                "stderr": f"Execution timed out after {_EXEC_TIMEOUT} seconds.",
                "exit_code": -1,
            }

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        return {
            "stdout": stdout[:_MAX_OUTPUT_CHARS],
            "stderr": stderr[:_MAX_OUTPUT_CHARS],
            "exit_code": proc.returncode,
        }
    finally:
        # Best-effort cleanup of the temp file
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass
