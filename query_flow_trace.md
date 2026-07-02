# Query Flow Trace: Frontend → Backend

## Overview

This document traces the complete lifecycle of a user query through the RAG chatbot system, from the moment the user hits Send to the final rendered response.

---

## Step 1 — User Input (frontend/script.js:45)

The user types a message and presses Enter or clicks the Send button. Both events call `sendMessage()`.

```js
// frontend/script.js:45
async function sendMessage() {
    const query = chatInput.value.trim();
    if (!query) return;

    chatInput.disabled = true;
    sendButton.disabled = true;

    addMessage(query, 'user');
    const loadingMessage = createLoadingMessage();
    chatMessages.appendChild(loadingMessage);

    const response = await fetch(`${API_URL}/query`, {   // API_URL = '/api'
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: query,
            session_id: currentSessionId   // null on first message
        })
    });
    ...
}
```

**What leaves the browser:**
```
POST /api/query
Content-Type: application/json

{ "query": "What is covered in lesson 2?", "session_id": null }
```

---

## Step 2 — FastAPI Endpoint (backend/app.py:56)

FastAPI receives the POST and deserialises the body into a `QueryRequest` Pydantic model.

```python
# backend/app.py:56
@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    session_id = request.session_id
    if not session_id:
        session_id = rag_system.session_manager.create_session()  # e.g. "session_1"

    answer, sources = rag_system.query(request.query, session_id)

    return QueryResponse(
        answer=answer,
        sources=sources,
        session_id=session_id
    )
```

If `session_id` is `None` (first message), `SessionManager.create_session()` generates a new ID (`session_1`, `session_2`, …) and registers an empty message list for it.

---

## Step 3 — RAG Orchestration (backend/rag_system.py:102)

`RAGSystem.query()` is the central coordinator. It:

1. Wraps the raw query in a prompt string
2. Retrieves conversation history for the session
3. Calls the AI generator with the search tool available

```python
# backend/rag_system.py:102
def query(self, query: str, session_id: Optional[str] = None) -> Tuple[str, List[str]]:
    prompt = f"""Answer this question about course materials: {query}"""

    history = None
    if session_id:
        history = self.session_manager.get_conversation_history(session_id)

    response = self.ai_generator.generate_response(
        query=prompt,
        conversation_history=history,
        tools=self.tool_manager.get_tool_definitions(),
        tool_manager=self.tool_manager
    )

    sources = self.tool_manager.get_last_sources()
    self.tool_manager.reset_sources()

    if session_id:
        self.session_manager.add_exchange(session_id, query, response)

    return response, sources
```

**`SessionManager.get_conversation_history()`** (backend/session_manager.py:42) returns the prior turns as a plain formatted string:
```
User: What topics are covered?
Assistant: The course covers ...
User: Tell me about lesson 2.
Assistant: Lesson 2 focuses on ...
```
History is capped at `MAX_HISTORY * 2` messages (default: 10 messages / 5 exchanges).

---

## Step 4 — First Claude API Call (backend/ai_generator.py:43)

`AIGenerator.generate_response()` assembles and fires the first Anthropic API request.

```python
# backend/ai_generator.py:43
def generate_response(self, query, conversation_history=None, tools=None, tool_manager=None):
    system_content = (
        f"{self.SYSTEM_PROMPT}\n\nPrevious conversation:\n{conversation_history}"
        if conversation_history
        else self.SYSTEM_PROMPT
    )

    api_params = {
        "model": self.model,           # e.g. claude-sonnet-4-6
        "temperature": 0,
        "max_tokens": 800,
        "messages": [{"role": "user", "content": query}],
        "system": system_content,
        "tools": tools,                # search_course_content tool schema
        "tool_choice": {"type": "auto"}
    }

    response = self.client.messages.create(**api_params)

    if response.stop_reason == "tool_use" and tool_manager:
        return self._handle_tool_execution(response, api_params, tool_manager)

    return response.content[0].text   # direct answer — no search needed
```

**The system prompt** instructs Claude to:
- Answer general questions from its own knowledge (no tool use)
- Use the `search_course_content` tool for course-specific questions (one search max)
- Never expose its reasoning process in the response

**Outcome — two branches:**

| `stop_reason`  | Meaning                                  | Next step                          |
|----------------|------------------------------------------|------------------------------------|
| `"end_turn"`   | Claude answered without searching        | Return `response.content[0].text`  |
| `"tool_use"`   | Claude needs to search course materials  | `_handle_tool_execution()`         |

---

## Step 5 — Tool Execution (backend/ai_generator.py:89)

When `stop_reason == "tool_use"`, `_handle_tool_execution()` takes over.

```python
# backend/ai_generator.py:89
def _handle_tool_execution(self, initial_response, base_params, tool_manager):
    messages = base_params["messages"].copy()

    # Append Claude's tool-use request as the assistant turn
    messages.append({"role": "assistant", "content": initial_response.content})

    # Execute each tool call and collect results
    tool_results = []
    for content_block in initial_response.content:
        if content_block.type == "tool_use":
            tool_result = tool_manager.execute_tool(
                content_block.name,        # "search_course_content"
                **content_block.input      # {query, course_name?, lesson_number?}
            )
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": content_block.id,
                "content": tool_result
            })

    # Append tool results as the next user turn
    messages.append({"role": "user", "content": tool_results})

    # Second API call — no tools this time, just synthesise results
    final_params = {**self.base_params, "messages": messages, "system": base_params["system"]}
    final_response = self.client.messages.create(**final_params)
    return final_response.content[0].text
```

---

## Step 6 — Vector Search (backend/search_tools.py:52 → backend/vector_store.py)

`tool_manager.execute_tool("search_course_content", ...)` dispatches to `CourseSearchTool.execute()`.

```python
# backend/search_tools.py:52
def execute(self, query: str, course_name=None, lesson_number=None) -> str:
    results = self.store.search(
        query=query,
        course_name=course_name,
        lesson_number=lesson_number
    )

    if results.error:
        return results.error

    if results.is_empty():
        return f"No relevant content found..."

    return self._format_results(results)
```

**`VectorStore.search()`** performs a semantic similarity search against ChromaDB using the configured embedding model. Results are filtered by `course_name` and/or `lesson_number` if Claude supplied them.

**`_format_results()`** (search_tools.py:88) builds the context string passed back to Claude:
```
[Introduction to MCP - Lesson 2]
MCP stands for Model Context Protocol. It defines how ...

[Introduction to MCP - Lesson 2]
The key components of MCP are ...
```
It also populates `self.last_sources` with human-readable labels like `"Introduction to MCP - Lesson 2"` for display in the UI.

---

## Step 7 — Second Claude API Call (backend/ai_generator.py:127)

The conversation now has three turns:
```
user:      "Answer this question about course materials: What is covered in lesson 2?"
assistant: [tool_use block — search_course_content]
user:      [tool_result block — formatted chunks from ChromaDB]
```

Claude synthesises the retrieved content into a final natural-language answer and returns `stop_reason == "end_turn"`.

---

## Step 8 — Unwinding to the Endpoint (backend/rag_system.py:130)

Back in `RAGSystem.query()`:

```python
sources = self.tool_manager.get_last_sources()   # ["Intro to MCP - Lesson 2", ...]
self.tool_manager.reset_sources()                # clear for next query

self.session_manager.add_exchange(session_id, query, response)  # persist Q&A to history

return response, sources
```

`app.py` serialises the result:
```python
return QueryResponse(answer=answer, sources=sources, session_id=session_id)
```

**HTTP response:**
```json
{
  "answer": "Lesson 2 covers the core components of MCP including...",
  "sources": ["Introduction to MCP - Lesson 2"],
  "session_id": "session_1"
}
```

---

## Step 9 — Rendering the Response (frontend/script.js:76)

```js
// frontend/script.js:76
const data = await response.json();

if (!currentSessionId) {
    currentSessionId = data.session_id;   // save for subsequent requests
}

loadingMessage.remove();
addMessage(data.answer, 'assistant', data.sources);
```

**`addMessage()`** (script.js:113):
- Renders `data.answer` as Markdown via `marked.parse()`
- If `data.sources` is non-empty, appends a collapsible `<details>` element listing the source labels

---

## End-to-End Diagram

```
Browser
  │
  │  User types query + presses Enter
  │
  ▼
sendMessage()                          frontend/script.js:45
  │  POST /api/query {query, session_id}
  ▼
query_documents()                      backend/app.py:56
  │  create session if needed
  │
  ▼
RAGSystem.query()                      backend/rag_system.py:102
  │  get conversation history
  │
  ▼
AIGenerator.generate_response()        backend/ai_generator.py:43
  │  1st Claude API call
  │  (system prompt + history + tools)
  │
  ├─── stop_reason == "end_turn" ──────────────────────────────────────┐
  │                                                                     │
  └─── stop_reason == "tool_use"                                       │
         │                                                             │
         ▼                                                             │
  _handle_tool_execution()             backend/ai_generator.py:89     │
         │  dispatch tool calls                                        │
         ▼                                                             │
  CourseSearchTool.execute()           backend/search_tools.py:52     │
         │                                                             │
         ▼                                                             │
  VectorStore.search()                 backend/vector_store.py        │
  (ChromaDB semantic search)                                           │
         │  formatted chunks + sources                                 │
         ▼                                                             │
  2nd Claude API call                  backend/ai_generator.py:127    │
  (synthesise tool results)                                            │
         │                                                             │
         └─────────────────────────────────────────────────────────────┘
                                       final answer text
                                             │
                                             ▼
                              collect sources, update session history
                                             │
                                             ▼
                              QueryResponse {answer, sources, session_id}
                                             │
                                             ▼
                              addMessage() — render Markdown + sources
                                          frontend/script.js:113
```

---

## Key Files Reference

| File | Role |
|---|---|
| `frontend/script.js` | User interaction, HTTP fetch, response rendering |
| `backend/app.py` | FastAPI routing, request/response models |
| `backend/rag_system.py` | Top-level orchestrator |
| `backend/ai_generator.py` | Claude API calls, tool execution loop |
| `backend/search_tools.py` | `CourseSearchTool` + `ToolManager` |
| `backend/vector_store.py` | ChromaDB semantic search |
| `backend/session_manager.py` | Conversation history storage |
| `backend/document_processor.py` | Ingestion-time chunking (not in query path) |
