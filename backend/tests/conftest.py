"""Shared pytest fixtures for the RAG chatbot test suite.

Note: backend/app.py mounts StaticFiles at "/" pointing at "../frontend",
which does not exist in the test environment and would fail at import time.
Rather than importing app.py directly, `test_app` below builds a standalone
FastAPI app that mirrors the real endpoints but is backed by an injected
mock RAGSystem, so API tests never touch static file mounting, ChromaDB,
or the Anthropic API.
"""
from typing import List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults


@pytest.fixture
def sample_lessons() -> List[Lesson]:
    return [
        Lesson(lesson_number=1, title="Introduction", lesson_link="https://example.com/lesson1"),
        Lesson(lesson_number=2, title="Advanced Topics", lesson_link="https://example.com/lesson2"),
    ]


@pytest.fixture
def sample_course(sample_lessons) -> Course:
    return Course(
        title="Test Course: Building RAG Systems",
        course_link="https://example.com/course",
        instructor="Jane Doe",
        lessons=sample_lessons,
    )


@pytest.fixture
def sample_course_chunks(sample_course) -> List[CourseChunk]:
    return [
        CourseChunk(
            content="Lesson 1 content: This is an introduction to RAG systems.",
            course_title=sample_course.title,
            lesson_number=1,
            chunk_index=0,
        ),
        CourseChunk(
            content="This covers advanced retrieval techniques.",
            course_title=sample_course.title,
            lesson_number=2,
            chunk_index=1,
        ),
    ]


@pytest.fixture
def sample_search_results(sample_course) -> SearchResults:
    return SearchResults(
        documents=["Lesson 1 content: This is an introduction to RAG systems."],
        metadata=[{"course_title": sample_course.title, "lesson_number": 1, "chunk_index": 0}],
        distances=[0.1],
    )


@pytest.fixture
def empty_search_results() -> SearchResults:
    return SearchResults(documents=[], metadata=[], distances=[])


@pytest.fixture
def error_search_results() -> SearchResults:
    return SearchResults.empty("No course found matching 'Nonexistent'")


@pytest.fixture
def mock_vector_store(sample_search_results, sample_course):
    """A MagicMock standing in for VectorStore, for tests that shouldn't touch ChromaDB."""
    store = MagicMock()
    store.search.return_value = sample_search_results
    store.get_lesson_link.return_value = "https://example.com/lesson1"
    store.get_course_link.return_value = sample_course.course_link
    store.get_existing_course_titles.return_value = [sample_course.title]
    store.get_course_count.return_value = 1
    return store


@pytest.fixture
def mock_anthropic_client():
    """Patches anthropic.Anthropic so AIGenerator never makes a real network call."""
    with patch("ai_generator.anthropic.Anthropic") as mock_anthropic_cls:
        client_instance = MagicMock()
        mock_anthropic_cls.return_value = client_instance
        yield client_instance


@pytest.fixture
def mock_rag_system(sample_course):
    """A MagicMock standing in for RAGSystem, used to back the API test app."""
    rag = MagicMock()
    rag.query.return_value = (
        "This is a test answer about RAG systems.",
        [{"text": f"{sample_course.title} - Lesson 1", "link": "https://example.com/lesson1"}],
    )
    rag.get_course_analytics.return_value = {
        "total_courses": 1,
        "course_titles": [sample_course.title],
    }
    rag.session_manager.create_session.return_value = "session_1"
    return rag


def _build_test_app(rag_system) -> FastAPI:
    """Recreates the API routes from backend/app.py against an injected
    rag_system, without mounting static files.
    """
    app = FastAPI(title="Course Materials RAG System (test)")

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class SourceItem(BaseModel):
        text: str
        link: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceItem]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    @app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = rag_system.session_manager.create_session()

            answer, sources = rag_system.query(request.query, session_id)

            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/")
    async def root():
        return {"message": "Course Materials RAG System API"}

    return app


@pytest.fixture
def test_app(mock_rag_system):
    return _build_test_app(mock_rag_system)


@pytest.fixture
def client(test_app):
    return TestClient(test_app)
