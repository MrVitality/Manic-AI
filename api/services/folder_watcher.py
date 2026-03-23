"""Watch-Folder Auto-Ingestion service.

Polls the `./inbox/` directory every 30 seconds. When new files are found they
are read, ingested via `ingest_document()`, then moved to `./inbox/done/` on
success or `./inbox/failed/` on error.

Supported extensions: .txt, .md, .pdf, .html, .docx

The watcher is started from the FastAPI lifespan and runs as a single asyncio
background task. File I/O is done in a thread pool executor so it never blocks
the event loop.
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from api.schemas.ingest import IngestRequest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INBOX_DIR = Path("inbox")
DONE_DIR = INBOX_DIR / "done"
FAILED_DIR = INBOX_DIR / "failed"

POLL_INTERVAL_SECONDS = 30

_SUPPORTED_EXTENSIONS = {".txt", ".md", ".pdf", ".html", ".docx"}

# Map file extensions to MIME content-types expected by ingest_document.
_CONTENT_TYPE_MAP = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".html": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

_watcher_task: Optional[asyncio.Task] = None


# ---------------------------------------------------------------------------
# Directory setup
# ---------------------------------------------------------------------------

def _ensure_directories() -> None:
    """Create inbox subdirectories if they don't already exist."""
    for directory in (INBOX_DIR, DONE_DIR, FAILED_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# File processing helpers
# ---------------------------------------------------------------------------

def _read_file_sync(path: Path) -> bytes:
    """Read a file as raw bytes (called in thread pool)."""
    return path.read_bytes()


def _move_file_sync(src: Path, dst_dir: Path) -> None:
    """Move a file to a destination directory (called in thread pool).

    Appends a UTC timestamp to avoid name collisions in done/failed dirs.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    dst = dst_dir / f"{timestamp}_{src.name}"
    shutil.move(str(src), str(dst))


def _list_inbox_sync() -> list[Path]:
    """Return supported files present in the inbox root (not subdirs)."""
    try:
        return [
            INBOX_DIR / name
            for name in os.listdir(INBOX_DIR)
            if (INBOX_DIR / name).is_file()
            and Path(name).suffix.lower() in _SUPPORTED_EXTENSIONS
        ]
    except OSError:
        logger.warning("folder_watcher: cannot read inbox directory")
        return []


# ---------------------------------------------------------------------------
# Per-file ingestion
# ---------------------------------------------------------------------------

async def _process_file(
    path: Path,
    http_client: httpx.AsyncClient,
    db_pool: Any,
) -> None:
    """Ingest a single file and move it to done/ or failed/."""
    loop = asyncio.get_running_loop()
    filename = path.name
    suffix = path.suffix.lower()
    content_type = _CONTENT_TYPE_MAP.get(suffix, "text/plain")

    logger.info("folder_watcher: processing %s", filename)

    try:
        raw_bytes: bytes = await loop.run_in_executor(None, _read_file_sync, path)

        # For text-based formats, decode to string. For binary (pdf/docx) the
        # preprocessor inside ingest_document handles bytes-as-base64 or raw text
        # extraction. We pass the raw bytes decoded as latin-1 so no data is lost.
        if suffix in (".txt", ".md", ".html"):
            content = raw_bytes.decode("utf-8", errors="replace")
        else:
            # Binary formats: pass bytes round-tripped through latin-1.
            # The preprocessor (detect_and_extract) handles PDF/DOCX extraction.
            content = raw_bytes.decode("latin-1")

        from api.services.ingestion import ingest_document

        request = IngestRequest(
            content=content,
            filename=filename,
            content_type=content_type,
            metadata={
                "source": "folder_watcher",
                "original_path": path.name,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        await ingest_document(request, db_pool, http_client)

        # Success — move to done/
        await loop.run_in_executor(None, _move_file_sync, path, DONE_DIR)
        logger.info("folder_watcher: successfully ingested %s", filename)

    except Exception:
        logger.exception("folder_watcher: failed to ingest %s", filename)
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _move_file_sync, path, FAILED_DIR)
        except Exception:
            logger.exception(
                "folder_watcher: could not move %s to failed/", filename
            )


# ---------------------------------------------------------------------------
# Background poll loop
# ---------------------------------------------------------------------------

async def _watcher_loop(http_client: httpx.AsyncClient, db_pool: Any) -> None:
    """Infinite loop that scans the inbox and processes new files."""
    logger.info("folder_watcher: started — watching %s", INBOX_DIR.resolve())
    loop = asyncio.get_running_loop()

    # Ensure inbox structure exists before first scan.
    await loop.run_in_executor(None, _ensure_directories)

    while True:
        try:
            files: list[Path] = await loop.run_in_executor(
                None, _list_inbox_sync
            )
            if files:
                logger.info(
                    "folder_watcher: found %d file(s) to process", len(files)
                )
                # Process files sequentially to avoid overwhelming the embedding
                # service with concurrent requests from large batches.
                for file_path in files:
                    await _process_file(file_path, http_client, db_pool)
        except Exception:
            logger.exception("folder_watcher: unexpected error in poll loop")

        await asyncio.sleep(POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

def start_folder_watcher(http_client: httpx.AsyncClient, db_pool: Any) -> asyncio.Task:
    """Start the folder-watcher background task and return it."""
    global _watcher_task
    _watcher_task = asyncio.create_task(
        _watcher_loop(http_client, db_pool),
        name="folder-watcher",
    )
    return _watcher_task


async def stop_folder_watcher() -> None:
    """Cancel the folder-watcher task gracefully."""
    global _watcher_task
    if _watcher_task and not _watcher_task.done():
        _watcher_task.cancel()
        try:
            await _watcher_task
        except asyncio.CancelledError:
            pass
    _watcher_task = None
    logger.info("folder_watcher: stopped")
