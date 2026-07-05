"""API endpoint tests.

These exercise the FastAPI routes from backend/app.py (POST /api/query,
GET /api/courses, GET /) against the `client` fixture, which is a TestClient
wrapping a standalone app (see conftest._build_test_app) backed by a mocked
RAGSystem. This sidesteps app.py's static file mount, which points at
"../frontend" and doesn't exist in the test environment.
"""
import pytest


pytestmark = pytest.mark.api


class TestQueryEndpoint:
    def test_query_with_new_session_creates_session_id(self, client, mock_rag_system):
        response = client.post("/api/query", json={"query": "What is RAG?"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "This is a test answer about RAG systems."
        assert data["session_id"] == "session_1"
        assert len(data["sources"]) == 1
        assert data["sources"][0]["text"].endswith("Lesson 1")
        mock_rag_system.session_manager.create_session.assert_called_once()
        mock_rag_system.query.assert_called_once_with("What is RAG?", "session_1")

    def test_query_with_existing_session_reuses_it(self, client, mock_rag_system):
        response = client.post(
            "/api/query", json={"query": "Follow up", "session_id": "existing_session"}
        )

        assert response.status_code == 200
        assert response.json()["session_id"] == "existing_session"
        mock_rag_system.session_manager.create_session.assert_not_called()
        mock_rag_system.query.assert_called_once_with("Follow up", "existing_session")

    def test_query_source_without_link_is_allowed(self, client, mock_rag_system):
        mock_rag_system.query.return_value = ("An answer with no link source.", [{"text": "Some Course"}])

        response = client.post("/api/query", json={"query": "anything"})

        assert response.status_code == 200
        assert response.json()["sources"] == [{"text": "Some Course", "link": None}]

    def test_query_missing_query_field_returns_422(self, client):
        response = client.post("/api/query", json={})
        assert response.status_code == 422

    def test_query_propagates_rag_system_errors_as_500(self, client, mock_rag_system):
        mock_rag_system.query.side_effect = RuntimeError("something went wrong")

        response = client.post("/api/query", json={"query": "anything"})

        assert response.status_code == 500
        assert response.json()["detail"] == "something went wrong"


class TestCoursesEndpoint:
    def test_get_course_stats_returns_analytics(self, client, mock_rag_system, sample_course):
        response = client.get("/api/courses")

        assert response.status_code == 200
        data = response.json()
        assert data["total_courses"] == 1
        assert data["course_titles"] == [sample_course.title]

    def test_get_course_stats_propagates_errors_as_500(self, client, mock_rag_system):
        mock_rag_system.get_course_analytics.side_effect = RuntimeError("db unavailable")

        response = client.get("/api/courses")

        assert response.status_code == 500
        assert response.json()["detail"] == "db unavailable"


class TestRootEndpoint:
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Course Materials RAG System API"}
