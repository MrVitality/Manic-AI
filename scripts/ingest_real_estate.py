#!/usr/bin/env python3
"""Bulk-ingest the Real_Estate/ source folder into Manic-AI's RAG layer.

Usage (on Windows dev box):
    python scripts/ingest_real_estate.py \\
        --source "C:/Users/mark_/Downloads/Real_Estate" \\
        --api http://100.98.154.61:8081 \\
        --api-key "$MANIC_API_KEY"

Usage (on VPS):
    python scripts/ingest_real_estate.py \\
        --source ~/Real_Estate \\
        --api http://localhost:8081

Collections:
    re_listings_past   -- Mark's past listing folders (3 addresses)
    re_training_sales  -- Brandon Mulrenin Reverse Selling + Top Dollar Blueprint
    re_geography       -- 20251213_all_locations.txt (structured per locality)
    re_compliance      -- minimal HUD Fair Housing seed (embedded below)

Idempotency: SHA-256 of file content becomes part of the filename sent to
`/v1/ingest`. Re-running will overwrite documents with the same hash in the
server-side dedup window (the API computes its own content_hash on storage).

Scope: .txt, .md, .markdown, .html ingested directly. .pdf and .docx are
LOGGED as skipped with a "manual ingest needed" note -- solo-op MVP keeps
dependencies minimal. Extend when the feed swap lands.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    print("httpx is required: pip install httpx", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("ingest_real_estate")

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm"}
SKIP_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".pptx"}
BINARY_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".avi",
    ".zip", ".tar", ".gz", ".exe", ".bin", ".dll", ".ico", ".ttf",
}

COLLECTIONS = {
    "re_listings_past": "Mark's past real estate listings (Vera Cohen Realty, Capital Region NY)",
    "re_training_sales": "Real estate sales training: Reverse Selling, Top Dollar Blueprint",
    "re_geography": "Capital Region geography and target locality data",
    "re_compliance": "HUD Fair Housing advertising guidance (seed corpus)",
    "re_market_intel": "Weekly market snapshots (populated by n8n WF07)",
}

# Minimal HUD Fair Housing seed. The Phase 2 critic retrieves from here;
# expand with the full HUD advertising guidance PDFs as a Phase 2 task.
HUD_FAIR_HOUSING_SEED = """\
# Fair Housing Act — Advertising Compliance (HUD seed)

## Protected classes (federal)
The Fair Housing Act prohibits discrimination in real estate advertising
based on: race, color, national origin, religion, sex (including sexual
orientation and gender identity), familial status (presence of children),
and disability. Many states and localities add additional protected classes
such as source of income, marital status, age, military status, and
citizenship/immigration status. New York State adds: age, marital status,
military status, sexual orientation, gender identity or expression,
domestic violence victim status, source of income, lawful occupation,
disability, and familial status.

## Prohibited language in listing copy
Avoid any language that expresses a preference, limitation, or
discrimination based on a protected class. This includes indirect cues:
- "Perfect for a young professional couple" (age / familial status)
- "Ideal for an empty-nester" (familial status / age)
- "Walking distance to St. Mary's" (religion, if used as a preference)
- "Great for a quiet single person" (familial status)
- "Master bedroom" is generally acceptable but increasingly replaced by
  "primary bedroom"; follow local convention
- "Mother-in-law suite" is acceptable; "nanny quarters" is risky
- Avoid references to specific ethnic or religious neighborhoods as
  selling points ("Jewish community", "Italian neighborhood")
- Avoid terms implying physical ability: "walkable", "climb to view"
  without noting elevator/accessibility alternatives

## Safe reframings
- Instead of "perfect family home" -> describe features: "four bedrooms,
  fenced yard, top-rated school district"
- Instead of "bachelor pad" -> "open-concept loft with city views"
- Instead of "quiet building, no kids" -> "well-maintained community"

## Accessibility claims
If a listing is marketed as accessible, claims must be verifiable:
no-step entries, wide doorways (32"+), roll-in showers, grab bars.
Do not use "handicapped accessible" -- prefer "accessible" or
"step-free entry".

## Equal Housing Opportunity logo/statement
All advertising should include the Equal Housing Opportunity logo or
statement where space permits. Digital listings: include in footer.

## Steering
Do not direct clients toward or away from neighborhoods based on
protected-class demographics. Describe neighborhoods factually
(schools, amenities, transit) without demographic characterization.

## References
- 42 U.S.C. § 3604 (Fair Housing Act)
- 24 C.F.R. § 100.75 (HUD advertising regulations)
- NAR Code of Ethics, Article 10
- New York State Human Rights Law, Article 15
"""


@dataclass(frozen=True)
class FileToIngest:
    path: Path
    collection: str
    relative: Path


def classify_collection(path: Path, source_root: Path) -> Optional[str]:
    """Decide which RAG collection a file belongs to based on folder layout."""
    try:
        rel = path.relative_to(source_root)
    except ValueError:
        return None
    top = rel.parts[0].lower() if rel.parts else ""

    if top == "documents" and path.name == "20251213_all_locations.txt":
        return "re_geography"
    if "mulrenin" in top or "reverseselling" in top or "top-dollar" in top:
        return "re_training_sales"
    # Listing folders are lowercase-dashed or underscored addresses
    if any(
        marker in top
        for marker in ("rockport", "livingston", "colonie_st", "_ave", "_ct", "_st")
    ):
        return "re_listings_past"
    # Anything else with a text extension goes to re_training_sales as default
    return "re_training_sales"


def iter_files(root: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            yield Path(dirpath) / name


def should_ingest(path: Path) -> bool:
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return True
    return False


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]


def read_text(path: Path) -> Optional[str]:
    for encoding in ("utf-8", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    logger.warning("Could not decode %s with any known encoding", path)
    return None


def ensure_collection(
    client: httpx.Client,
    api_base: str,
    headers: dict[str, str],
    name: str,
    description: str,
) -> Optional[str]:
    """Create a collection if missing, return its id."""
    try:
        resp = client.get(f"{api_base}/v1/collections", headers=headers)
        resp.raise_for_status()
        existing = resp.json().get("data") or []
        for c in existing:
            if c.get("name") == name:
                return c.get("id")
    except httpx.HTTPError as exc:
        logger.warning("Could not list collections: %s -- attempting to create", exc)

    try:
        resp = client.post(
            f"{api_base}/v1/collections",
            headers=headers,
            json={"name": name, "description": description},
        )
        if resp.status_code in (200, 201):
            body = resp.json().get("data") or {}
            return body.get("id")
        logger.warning("Create collection %s returned %d: %s", name, resp.status_code, resp.text[:200])
    except httpx.HTTPError as exc:
        logger.error("Failed to create collection %s: %s", name, exc)
    return None


def ingest_text(
    client: httpx.Client,
    api_base: str,
    headers: dict[str, str],
    collection_id: Optional[str],
    filename: str,
    content: str,
    metadata: dict,
) -> bool:
    payload = {
        "content": content,
        "filename": filename,
        "content_type": "text/plain",
        "collection_id": collection_id,
        "metadata": metadata,
        "chunk_size": 800,
        "chunk_overlap": 100,
        "backend": "supabase",
        "chunking_strategy": "semantic",
    }
    try:
        resp = client.post(f"{api_base}/v1/ingest", headers=headers, json=payload, timeout=300)
        if resp.status_code in (200, 202):
            logger.info("  ingested %s -> %s", filename, resp.json().get("data", {}).get("document_id", "?"))
            return True
        logger.error("  ingest failed %s: %d %s", filename, resp.status_code, resp.text[:200])
        return False
    except httpx.HTTPError as exc:
        logger.error("  ingest error %s: %s", filename, exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Path to Real_Estate folder")
    parser.add_argument("--api", default="http://localhost:8081", help="Manic-AI API base URL")
    parser.add_argument("--api-key", default=os.environ.get("MANIC_API_KEY", ""), help="X-API-Key header")
    parser.add_argument("--dry-run", action="store_true", help="List files that would be ingested, no calls")
    parser.add_argument("--skip-compliance", action="store_true", help="Do not seed re_compliance")
    args = parser.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        logger.error("Source folder not found: %s", source)
        return 2

    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["X-API-Key"] = args.api_key

    logger.info("Source: %s", source)
    logger.info("API: %s", args.api)

    if args.dry_run:
        logger.info("DRY RUN -- no API calls will be made")

    # Count files by collection
    files: list[FileToIngest] = []
    skipped_pdfs: list[Path] = []
    skipped_other: list[Path] = []

    for path in iter_files(source):
        ext = path.suffix.lower()
        if should_ingest(path):
            collection = classify_collection(path, source)
            if not collection:
                skipped_other.append(path)
                continue
            files.append(FileToIngest(path=path, collection=collection, relative=path.relative_to(source)))
        elif ext in SKIP_EXTENSIONS:
            skipped_pdfs.append(path)
        else:
            skipped_other.append(path)

    logger.info("Plan: %d files to ingest, %d pdf/docx deferred, %d other skipped",
                len(files), len(skipped_pdfs), len(skipped_other))

    if args.dry_run:
        by_collection: dict[str, list[Path]] = {}
        for f in files:
            by_collection.setdefault(f.collection, []).append(f.relative)
        for col, paths in sorted(by_collection.items()):
            logger.info("  %s: %d files", col, len(paths))
            for p in paths[:10]:
                logger.info("    - %s", p)
            if len(paths) > 10:
                logger.info("    ... and %d more", len(paths) - 10)
        if skipped_pdfs:
            logger.info("Deferred (PDF/DOCX — require manual or multimodal ingest):")
            for p in skipped_pdfs[:20]:
                logger.info("  - %s", p.relative_to(source))
        return 0

    with httpx.Client(timeout=60.0) as client:
        # Ensure collections exist
        collection_ids: dict[str, Optional[str]] = {}
        for name, desc in COLLECTIONS.items():
            cid = ensure_collection(client, args.api, headers, name, desc)
            collection_ids[name] = cid
            logger.info("  collection %-20s -> %s", name, cid or "(created without id)")

        # Seed HUD Fair Housing
        if not args.skip_compliance:
            seed_hash = content_hash(HUD_FAIR_HOUSING_SEED.encode())
            ingest_text(
                client, args.api, headers,
                collection_ids.get("re_compliance"),
                filename=f"hud_fair_housing_seed_{seed_hash}.md",
                content=HUD_FAIR_HOUSING_SEED,
                metadata={
                    "source": "hud_seed",
                    "category": "fair_housing",
                    "jurisdiction": "federal+ny_state",
                    "version": "phase1_seed",
                },
            )

        # Ingest text files
        ok_count = 0
        fail_count = 0
        for f in files:
            content = read_text(f.path)
            if content is None:
                fail_count += 1
                continue
            h = content_hash(content.encode("utf-8", errors="ignore"))
            filename = f"{f.relative.as_posix().replace('/', '__')}__{h}{f.path.suffix}"
            metadata = {
                "source_path": str(f.relative),
                "source_folder": f.relative.parts[0] if f.relative.parts else "",
                "collection": f.collection,
                "content_hash": h,
            }
            if ingest_text(
                client, args.api, headers,
                collection_ids.get(f.collection),
                filename=filename,
                content=content,
                metadata=metadata,
            ):
                ok_count += 1
            else:
                fail_count += 1

        logger.info("Ingest complete: %d ok, %d failed", ok_count, fail_count)
        if skipped_pdfs:
            logger.info("Deferred PDF/DOCX files (ingest manually via UI or Phase 2 multimodal):")
            for p in skipped_pdfs:
                logger.info("  - %s", p.relative_to(source))

    return 0


if __name__ == "__main__":
    sys.exit(main())
