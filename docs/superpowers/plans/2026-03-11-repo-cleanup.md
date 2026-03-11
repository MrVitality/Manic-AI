# Repo Cleanup & Production Packaging Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the Manic-AI repository for sharing/publishing by removing junk files, organizing docs into `docs/FAQ/`, expanding `.gitignore`, and writing a proper README across exactly 5 atomic commits.

**Architecture:** Five sequential, atomic commits transform the repo from a development workspace into a clean publishable project. No application code (`api/`, `frontend/`) is modified. All moves use `git mv` to preserve history.

**Tech Stack:** Git (mv for history), bash shell, Markdown

**Spec:** `docs/superpowers/specs/2026-03-11-repo-cleanup-design.md`

---

## File Map

| Change | From | To |
|--------|------|----|
| DELETE | `manic@72.61.78.179` | (removed) |
| DELETE | `frontend/{app,components,lib,hooks,types,public,styles}/` | (removed) |
| DELETE | `frontend/{app,components,lib,hooks,types,public}/` | (removed) |
| DELETE | `frontend/{components,hooks,lib,public}/` | (removed) |
| MOVE | `dashboard-overview.png` | `docs/assets/dashboard-overview.png` |
| MOVE | `dashboard-services.png` | `docs/assets/dashboard-services.png` |
| MOVE | `rag-center.png` | `docs/assets/rag-center.png` |
| MOVE | `settings-view.png` | `docs/assets/settings-view.png` |
| MOVE | `INSTALL.md` | `docs/FAQ/install.md` |
| MOVE | `ARCHITECTURE_MAP.md` | `docs/FAQ/architecture.md` |
| MOVE | `RAG_GUIDE.md` | `docs/FAQ/rag-guide.md` |
| MOVE | `SUPABASE_SETUP.md` | `docs/FAQ/supabase-setup.md` |
| MOVE | `SERVICE_UTILIZATION_PLAN.md` | `docs/FAQ/services.md` |
| MOVE | `IMPLEMENTATION.md` | `docs/FAQ/implementation.md` |
| MOVE | `MANIC_AI_COMPLETE_GUIDE.md` | `docs/FAQ/complete-guide.md` |
| MOVE | `SKILLS.md` | `docs/FAQ/skills.md` |
| CREATE | (new) | `docs/FAQ/README.md` (index) |
| MODIFY | `.gitignore` | add tooling, build, secrets, OS entries |
| MODIFY | `README.md` | expand to full project overview |

---

## Chunk 1: Junk Removal

### Task 1: Delete junk files and ghost directories

**Files:**
- Delete: `manic@72.61.78.179`
- Delete: `frontend/{app,components,lib,hooks,types,public,styles}/`
- Delete: `frontend/{app,components,lib,hooks,types,public}/`
- Delete: `frontend/{components,hooks,lib,public}/`

- [ ] **Step 1: Verify junk targets exist**

  Run:
  ```bash
  ls -la "manic@72.61.78.179"
  ls -d "frontend/{app,components,lib,hooks,types,public,styles}"
  ls -d "frontend/{app,components,lib,hooks,types,public}"
  ls -d "frontend/{components,hooks,lib,public}"
  ```
  Expected: All four items listed without error.

- [ ] **Step 2: Remove the junk SQL file via git**

  Run:
  ```bash
  git rm "manic@72.61.78.179"
  ```
  Expected: `rm 'manic@72.61.78.179'`

- [ ] **Step 3: Remove ghost directories from disk**

  Run (double-quoted to prevent shell brace expansion):
  ```bash
  rm -rf "frontend/{app,components,lib,hooks,types,public,styles}"
  rm -rf "frontend/{app,components,lib,hooks,types,public}"
  rm -rf "frontend/{components,hooks,lib,public}"
  ```
  Expected: Removed silently.

- [ ] **Step 4: Stage ghost directory removal**

  Run:
  ```bash
  git add -A frontend/
  ```
  Expected: No error output.

- [ ] **Step 5: Verify only junk is staged**

  Run:
  ```bash
  git diff --cached --name-only
  ```
  Expected: `manic@72.61.78.179` deleted + 3 ghost dirs deleted. Nothing else.

- [ ] **Step 6: Commit**

  Run:
  ```bash
  git commit -m "chore: delete junk files and empty ghost directories"
  ```
  Expected: `[main <hash>] chore: delete junk files and empty ghost directories`

---

## Chunk 2: Screenshot Organization

### Task 2: Move root screenshots to docs/assets/

**Files:**
- Create: `docs/assets/` directory
- Move: `dashboard-overview.png` to `docs/assets/dashboard-overview.png`
- Move: `dashboard-services.png` to `docs/assets/dashboard-services.png`
- Move: `rag-center.png` to `docs/assets/rag-center.png`
- Move: `settings-view.png` to `docs/assets/settings-view.png`

- [ ] **Step 1: Verify PNGs exist at root**

  Run:
  ```bash
  ls -la *.png
  ```
  Expected: 4 PNG files listed.

- [ ] **Step 2: Create docs/assets/ directory**

  Run:
  ```bash
  mkdir -p docs/assets
  ```
  Expected: Created silently.

- [ ] **Step 3: Move PNGs with git history preservation**

  Run:
  ```bash
  git mv dashboard-overview.png docs/assets/dashboard-overview.png
  git mv dashboard-services.png docs/assets/dashboard-services.png
  git mv rag-center.png docs/assets/rag-center.png
  git mv settings-view.png docs/assets/settings-view.png
  ```
  Expected: Each exits 0 silently.

- [ ] **Step 4: Verify staged renames**

  Run:
  ```bash
  git status
  ```
  Expected: 4 lines of `renamed: *.png -> docs/assets/*.png`

- [ ] **Step 5: Commit**

  Run:
  ```bash
  git commit -m "chore: move screenshots to docs/assets/"
  ```
  Expected: `[main <hash>] chore: move screenshots to docs/assets/`

---

## Chunk 3: Documentation Organization

### Task 3: Move project guides into docs/FAQ/ with index

**Files:**
- Move: `INSTALL.md` to `docs/FAQ/install.md`
- Move: `ARCHITECTURE_MAP.md` to `docs/FAQ/architecture.md`
- Move: `RAG_GUIDE.md` to `docs/FAQ/rag-guide.md`
- Move: `SUPABASE_SETUP.md` to `docs/FAQ/supabase-setup.md`
- Move: `SERVICE_UTILIZATION_PLAN.md` to `docs/FAQ/services.md`
- Move: `IMPLEMENTATION.md` to `docs/FAQ/implementation.md`
- Move: `MANIC_AI_COMPLETE_GUIDE.md` to `docs/FAQ/complete-guide.md`
- Move: `SKILLS.md` to `docs/FAQ/skills.md`
- Create: `docs/FAQ/README.md` (table of contents)

- [ ] **Step 1: Verify all 8 source files exist**

  Run:
  ```bash
  ls -la INSTALL.md ARCHITECTURE_MAP.md RAG_GUIDE.md SUPABASE_SETUP.md \
         SERVICE_UTILIZATION_PLAN.md IMPLEMENTATION.md MANIC_AI_COMPLETE_GUIDE.md SKILLS.md
  ```
  Expected: All 8 files listed.

- [ ] **Step 2: Create docs/FAQ/ directory**

  Run:
  ```bash
  mkdir -p docs/FAQ
  ```
  Expected: Created silently.

- [ ] **Step 3: Move all 8 docs with git history preservation**

  Run:
  ```bash
  git mv INSTALL.md docs/FAQ/install.md
  git mv ARCHITECTURE_MAP.md docs/FAQ/architecture.md
  git mv RAG_GUIDE.md docs/FAQ/rag-guide.md
  git mv SUPABASE_SETUP.md docs/FAQ/supabase-setup.md
  git mv SERVICE_UTILIZATION_PLAN.md docs/FAQ/services.md
  git mv IMPLEMENTATION.md docs/FAQ/implementation.md
  git mv MANIC_AI_COMPLETE_GUIDE.md docs/FAQ/complete-guide.md
  git mv SKILLS.md docs/FAQ/skills.md
  ```
  Expected: Each exits 0 silently.

- [ ] **Step 4: Create docs/FAQ/README.md index**

  Write `docs/FAQ/README.md` with this content:

  ```markdown
  # Manic-AI Documentation

  | Guide | Description |
  |-------|-------------|
  | [Installation](install.md) | Setup and deployment instructions |
  | [Architecture](architecture.md) | System architecture and component map |
  | [RAG Guide](rag-guide.md) | Retrieval-Augmented Generation pipeline |
  | [Supabase Setup](supabase-setup.md) | Database configuration |
  | [Services](services.md) | Service utilization and configuration |
  | [Implementation](implementation.md) | Implementation details and decisions |
  | [Complete Guide](complete-guide.md) | Comprehensive platform guide |
  | [Skills](skills.md) | AI agent skills reference |
  ```

- [ ] **Step 5: Stage the index file**

  Run:
  ```bash
  git add docs/FAQ/README.md
  ```
  Expected: File staged.

- [ ] **Step 6: Verify staging: 8 renames + 1 new file**

  Run:
  ```bash
  git diff --cached --name-only
  ```
  Expected: 9 entries (8 renames + `docs/FAQ/README.md`).

- [ ] **Step 7: Commit**

  Run:
  ```bash
  git commit -m "docs: move project guides into docs/FAQ/ with index"
  ```
  Expected: `[main <hash>] docs: move project guides into docs/FAQ/ with index`

---

## Chunk 4: .gitignore Expansion

### Task 4: Expand .gitignore for tooling, build artifacts, and secrets

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Check current .gitignore content**

  Run:
  ```bash
  cat .gitignore
  ```
  Expected: Shows existing entries (if any). Note them to avoid duplicates.

- [ ] **Step 2: Append new entries**

  Append to `.gitignore` (after the last existing line):

  ```gitignore

  # AI Tooling (local dev only)
  .claude/
  .agent/
  .gemini/
  everything-claude-code/

  # Editor
  .vscode/
  .playwright-mcp/

  # Frontend build artifacts
  frontend/node_modules/
  frontend/.next/

  # Python
  __pycache__/
  *.pyc
  .venv/
  venv/

  # Environment & secrets
  .env
  .env.*
  !.env.example

  # OS
  .DS_Store
  Thumbs.db

  # Logs
  *.log
  ```

- [ ] **Step 3: Verify .gitignore diff**

  Run:
  ```bash
  git diff .gitignore
  ```
  Expected: Shows all new sections added.

- [ ] **Step 4: Spot-check that .claude/ is now gitignored**

  Run:
  ```bash
  git check-ignore -v .claude/settings.local.json
  ```
  Expected: `.gitignore:N:.claude/  .claude/settings.local.json`

- [ ] **Step 5: Stage and commit**

  Run:
  ```bash
  git add .gitignore
  git commit -m "chore: expand .gitignore for tooling, build artifacts, secrets"
  ```
  Expected: `[main <hash>] chore: expand .gitignore for tooling, build artifacts, secrets`

---

## Chunk 5: README Expansion

### Task 5: Expand README with project overview and quick-start

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Check current README content**

  Run:
  ```bash
  cat README.md
  ```
  Expected: Current content (approximately 12 bytes, essentially empty).

- [ ] **Step 2: Replace README.md with full project overview**

  Replace entire contents of `README.md` with:

  ```markdown
  # Manic-AI

  Full-stack AI platform with RAG (Retrieval-Augmented Generation) capabilities.

  ## Tech Stack

  | Layer | Technology |
  |-------|-----------|
  | Frontend | Next.js 14 + TypeScript + Tailwind CSS |
  | API | FastAPI (Python) |
  | Vector DB | Supabase (pgvector + BM25) + Qdrant |
  | LLM Inference | Ollama (local models) |
  | Infrastructure | Docker Compose (18 services) |

  ## Quick Start

  ```bash
  cp .env.example .env   # fill in your values
  docker compose up -d
  ```

  Open http://localhost:3000

  ## Documentation

  Full documentation is in [docs/FAQ/](docs/FAQ/README.md).

  ## License

  See [LICENSE](LICENSE).
  ```

- [ ] **Step 3: Verify README content**

  Run:
  ```bash
  cat README.md
  ```
  Expected: Full expanded content with tech stack table and quick-start instructions.

- [ ] **Step 4: Stage and commit**

  Run:
  ```bash
  git add README.md
  git commit -m "docs: expand README with project overview and quick-start"
  ```
  Expected: `[main <hash>] docs: expand README with project overview and quick-start`

---

## Final Verification

- [ ] **Verify all 5 commits landed**

  Run:
  ```bash
  git log --oneline -6
  ```
  Expected (newest first):
  ```
  <hash> docs: expand README with project overview and quick-start
  <hash> chore: expand .gitignore for tooling, build artifacts, secrets
  <hash> docs: move project guides into docs/FAQ/ with index
  <hash> chore: move screenshots to docs/assets/
  <hash> chore: delete junk files and empty ghost directories
  ```

- [ ] **Verify repo structure**

  Run:
  ```bash
  ls docs/FAQ/
  ls docs/assets/
  ls *.png 2>/dev/null && echo "FAIL: PNGs still at root" || echo "OK: no root PNGs"
  ```
  Expected:
  - `docs/FAQ/` has 9 files (README.md + 8 guides)
  - `docs/assets/` has 4 PNGs
  - No PNGs at root

- [ ] **Verify gitignored dirs are silent**

  Run:
  ```bash
  git status --short
  ```
  Expected: Clean working tree — `.claude/`, `.agent/`, `frontend/node_modules/`, `frontend/.next/` silently excluded.
