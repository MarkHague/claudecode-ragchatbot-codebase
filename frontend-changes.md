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

---

# Frontend Changes: Theme Toggle Button

## Summary
Added a light/dark theme toggle button so the UI is no longer locked to the dark theme. The toggle is a fixed, circular icon button in the top-right corner of the viewport, styled to match the existing send-button aesthetic (rounded, `--surface` background, `--primary-color` hover accent, focus ring).

## Files changed

### `frontend/index.html`
- Added a `<button id="themeToggle">` right after `<body>`, containing two inline SVG icons (sun / moon, Feather-icon style, matching the send button's `stroke="currentColor"` icon convention).
- Button includes `aria-label`, `aria-pressed`, and a `title` attribute for accessibility; label text is updated dynamically by JS to reflect the action the button performs.

### `frontend/style.css`
- Added a `:root[data-theme="light"]` block overriding the dark-theme CSS variables (`--background`, `--surface`, `--surface-hover`, `--text-primary`, `--text-secondary`, `--border-color`, `--assistant-message`, `--shadow`, `--focus-ring`, `--welcome-bg`) with light equivalents. Brand colors (`--primary-color`, `--primary-hover`, `--user-message`, `--welcome-border`) stay constant across themes.
- Added `.theme-toggle` styles: fixed position (top-right), circular button, hover/active/focus-visible states consistent with existing interactive elements (`#sendButton`, `.suggested-item`).
- Icon swap handled in pure CSS: `.theme-icon-moon` hidden by default; `[data-theme="light"]` flips which icon is visible (sun shown in dark mode as an affordance to switch to light, moon shown in light mode to switch back to dark).
- Added subtle `background-color`/`border-color`/`color` transitions to `body`, `.main-content`, and `.sidebar` so the theme switch animates instead of snapping.
- Added a small-screen rule shrinking the toggle button slightly under the existing `768px` breakpoint.

### `frontend/script.js`
- Added `themeToggle` to the cached DOM element references.
- Added `initTheme()`, `applyTheme(theme)`, and `toggleTheme()`:
  - `initTheme()` reads a saved theme from `localStorage` (defaulting to `dark`) and applies it on load, before the welcome message renders.
  - `applyTheme()` sets `data-theme` on `<html>`, updates `aria-pressed`/`aria-label` on the button, and persists the choice to `localStorage`.
  - `toggleTheme()` flips between `dark` and `light` and is wired to the button's `click` event in `setupEventListeners()`.

## Accessibility / keyboard navigation
- The toggle is a native `<button>` element, so it is reachable via Tab and activates on both `Enter` and `Space` without extra JS.
- `aria-pressed` reflects toggle state (`true` = light theme active) for assistive tech.
- `aria-label` updates to describe the action that will happen next ("Switch to light theme" / "Switch to dark theme").
- A visible `:focus-visible` ring (reusing the existing `--focus-ring` variable) shows keyboard focus, matching the focus treatment already used on `#chatInput`, `#sendButton`, and `.suggested-item`.

## Persistence
Theme choice is stored in `localStorage` under the `theme` key and restored on next visit/reload.
