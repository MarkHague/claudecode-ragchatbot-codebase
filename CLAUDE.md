# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
uv sync

# Run the server (from repo root)
./run.sh
# or manually:
cd backend && uv run uvicorn app:app --reload --port 8000
```

The app serves at `http://localhost:8000`. FastAPI interactive docs are at `http://localhost:8000/docs`.

**Required:** A `.env` file in the repo root with `ANTHROPIC_API_KEY=...` (see `.env.example`).

### Code quality

```bash
# Auto-format backend/ and main.py with black
./scripts/format.sh

# Check formatting only, no changes (exits non-zero on violations; use in CI)
./scripts/check.sh
```

Black is configured in `pyproject.toml` under `[tool.black]` (line-length 88). There are no tests and no other linter configured.

## Architecture

This is a full-stack RAG chatbot. FastAPI serves both the API (`/api/*`) and the static frontend (`frontend/`) from a single process. The server must be started from the `backend/` directory because `config.py` sets `CHROMA_PATH = "./chroma_db"` and `app.py` loads docs from `"../docs"` — both are relative to `backend/`.

### Core data flow

```
frontend/script.js  →  POST /api/query  →  RAGSystem.query()
                                               ├─ SessionManager  (conversation history)
                                               └─ AIGenerator.generate_response()
                                                       ├─ 1st Claude call  (with tool schema)
                                                       │    stop_reason == "tool_use"?
                                                       │      YES → CourseSearchTool.execute()
                                                       │               └─ VectorStore.search()  (ChromaDB)
                                                       │      → 2nd Claude call  (synthesise results)
                                                       └─ returns final text
```

### Two-turn Claude pattern

`AIGenerator` always makes an initial API call with the `search_course_content` tool available and `tool_choice: auto`. If Claude decides to search, `_handle_tool_execution()` runs the tool, appends the results as a `user` turn, then makes a second API call (without tools) to get the final answer. General-knowledge questions resolve in a single call.

### ChromaDB dual-collection design

`VectorStore` maintains two separate ChromaDB collections:

- **`course_catalog`** — one document per course (title text + metadata: instructor, course_link, lessons as a JSON-serialised string). Used only for semantic course-name resolution (`_resolve_course_name`).
- **`course_content`** — one document per text chunk, metadata: `course_title`, `lesson_number`, `chunk_index`. Used for all content queries.

Course titles are used as document IDs in `course_catalog`, so titles must be unique. Duplicate detection in `RAGSystem.add_course_folder()` is title-based.

### Document ingestion format

`DocumentProcessor.process_course_document()` expects plain-text files with this structure:

```
Course Title: <title>
Course Link: <url>
Course Instructor: <name>

Lesson 1: <lesson title>
Lesson Link: <url>
<lesson body text…>

Lesson 2: <lesson title>
…
```

Files in `docs/` are auto-loaded at server startup (`app.py` startup event). Already-indexed courses are skipped. To force a full re-index, call `vector_store.clear_all_data()` before ingestion or pass `clear_existing=True` to `add_course_folder()`.

### Key configuration (backend/config.py)

| Setting | Default | Effect |
|---|---|---|
| `ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Claude model used for generation |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for ChromaDB |
| `CHUNK_SIZE` | 800 chars | Max characters per vector chunk |
| `CHUNK_OVERLAP` | 100 chars | Sentence-level overlap between chunks |
| `MAX_RESULTS` | 5 | ChromaDB results returned per search |
| `MAX_HISTORY` | 2 | Conversation exchanges kept per session (×2 = messages) |
| `CHROMA_PATH` | `./chroma_db` | Persistent ChromaDB storage (relative to `backend/`) |

### Adding a new tool

1. Create a class that extends `Tool` (abstract base in `search_tools.py`) implementing `get_tool_definition()` and `execute()`.
2. Register it: `rag_system.tool_manager.register_tool(YourTool(...))` in `RAGSystem.__init__`.

If the tool needs to surface sources in the UI, add a `last_sources: list` attribute — `ToolManager.get_last_sources()` and `reset_sources()` pick it up automatically.
