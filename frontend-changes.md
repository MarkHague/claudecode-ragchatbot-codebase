# Testing Framework Enhancement

## Summary

Built out a complete pytest suite for the backend (`backend/tests/`) — none existed
previously in this worktree. Covers both unit tests for existing components and API
endpoint tests for the FastAPI app.

## Files added

- `backend/tests/__init__.py` — makes `tests` an importable package.
- `backend/tests/conftest.py` — shared fixtures: sample course/lesson/chunk data,
  `mock_vector_store`, `mock_anthropic_client`, `mock_rag_system`, and a `test_app` /
  `client` fixture pair backed by a standalone FastAPI app.
- `backend/tests/helpers.py` — `make_text_response` / `make_tool_use_response` builders
  for mock Anthropic API responses.
- `backend/tests/test_session_manager.py`
- `backend/tests/test_document_processor.py`
- `backend/tests/test_search_tools.py`
- `backend/tests/test_ai_generator.py`
- `backend/tests/test_vector_store.py`
- `backend/tests/test_rag_system.py`
- `backend/tests/test_api.py` — API endpoint tests for `POST /api/query`,
  `GET /api/courses`, and `GET /`.

## Files changed

- `pyproject.toml` — added `[tool.pytest.ini_options]` (`testpaths`, `pythonpath`,
  markers `unit`/`api`) and added `pytest`, `pytest-mock`, `httpx` as dev dependencies
  via `uv add --dev`.

## Key design decision: avoiding the static-file mount issue

`backend/app.py` mounts `StaticFiles(directory="../frontend")` at import time, which
fails in the test environment since that path doesn't exist there (and importing
`app.py` would also construct a real `RAGSystem`, hitting ChromaDB/Anthropic). Instead
of importing `app.py`, `conftest.py` defines `_build_test_app()`, a standalone FastAPI
app that mirrors the three real routes (`/api/query`, `/api/courses`, `/`) but takes an
injected `rag_system` and never mounts static files. The `client` fixture wraps it in a
`TestClient`.

## Test isolation

- `VectorStore` tests patch `chromadb.PersistentClient` and the sentence-transformer
  embedding function so no real ChromaDB/embedding model is loaded.
- `AIGenerator` tests patch `anthropic.Anthropic` so no real API calls are made.
- `RAGSystem` tests patch `VectorStore` and `AIGenerator` (the two components with
  external dependencies) while keeping `SessionManager`, `ToolManager`, and
  `CourseSearchTool` real.
- API tests use the mocked `RAGSystem` from `conftest.py`, so no component under test
  touches the network, disk-backed ChromaDB, or the Anthropic API.

## Verification

`uv run pytest` (from repo root) and `cd backend && uv run pytest` both pass:
58 passed, no stray `chroma_db` directories created as a side effect.
