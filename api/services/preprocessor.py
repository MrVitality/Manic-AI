"""Document preprocessing — extract plain text from various content types."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def extract_text_from_html(content: str) -> str:
    """Strip HTML tags and return plain text using BeautifulSoup."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.warning("beautifulsoup4 not installed; returning raw content")
        return content

    soup = BeautifulSoup(content, "html.parser")

    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    # Collapse blank lines
    lines = (line.strip() for line in text.splitlines())
    return "\n".join(line for line in lines if line)


def extract_text_from_markdown(content: str) -> str:
    """Return markdown content with YAML frontmatter stripped."""
    # Strip YAML frontmatter (--- delimited block at start)
    stripped = re.sub(r"\A---\s*\n.*?\n---\s*\n", "", content, count=1, flags=re.DOTALL)
    return stripped.strip()


def extract_text_from_docx(content_bytes: bytes) -> str:
    """Extract plain text from a .docx file's raw bytes."""
    try:
        from docx import Document
    except ImportError:
        logger.warning("python-docx not installed; cannot extract .docx content")
        return ""

    import io

    doc = Document(io.BytesIO(content_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def detect_and_extract(content: str, content_type: str) -> str:
    """Dispatch to the appropriate extractor based on content_type.

    Parameters
    ----------
    content:
        The raw document content as a string.
    content_type:
        MIME type or simple type hint (e.g. ``"text/html"``, ``"text/markdown"``).

    Returns
    -------
    str
        Extracted plain text suitable for chunking.
    """
    ct = content_type.lower().strip()

    if ct in ("text/html", "html"):
        return extract_text_from_html(content)

    if ct in ("text/markdown", "text/x-markdown", "markdown", "md"):
        return extract_text_from_markdown(content)

    # For plain text and unrecognised types, pass through unchanged
    return content
