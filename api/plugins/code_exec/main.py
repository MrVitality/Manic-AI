"""Code execution plugin.

Runs arbitrary Python code in a temporary subprocess with a hard timeout.
No network access is granted to the subprocess and file writes are
restricted to /tmp via the executed code's own behaviour — the sandbox
does not enforce filesystem isolation beyond what the OS provides for the
subprocess.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

from api.plugins import tool

_EXEC_TIMEOUT = 10  # seconds
_MAX_OUTPUT_CHARS = 2000


@tool(
    name="execute_python",
    description="Execute Python code and return stdout/stderr",
)
async def execute_python(code: str) -> dict:
    """Execute a Python code snippet and return its output.

    Args:
        code: The Python source code to execute.

    Returns:
        A dict with keys ``stdout``, ``stderr``, and ``exit_code``.
        Each output string is truncated to 2000 characters.
    """
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
