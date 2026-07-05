from unittest.mock import MagicMock, patch

import pytest

from models import Course, CourseChunk
from rag_system import RAGSystem


pytestmark = pytest.mark.unit


class FakeConfig:
    CHUNK_SIZE = 800
    CHUNK_OVERLAP = 100
    CHROMA_PATH = "/tmp/fake_chroma"
    EMBEDDING_MODEL = "fake-model"
    MAX_RESULTS = 5
    ANTHROPIC_API_KEY = "fake-key"
    ANTHROPIC_MODEL = "fake-model"
    MAX_HISTORY = 2


@pytest.fixture
def rag_system():
    """Builds a RAGSystem with VectorStore and AIGenerator replaced by mocks,
    since those touch ChromaDB and the Anthropic API respectively. SessionManager,
    DocumentProcessor, ToolManager, and CourseSearchTool remain real, lightweight objects.
    """
    with patch("rag_system.VectorStore") as MockVectorStore, patch(
        "rag_system.AIGenerator"
    ) as MockAIGenerator:
        MockVectorStore.return_value = MagicMock()
        MockAIGenerator.return_value = MagicMock()
        system = RAGSystem(FakeConfig())
        yield system


def test_query_without_session_omits_history(rag_system):
    rag_system.ai_generator.generate_response.return_value = "The answer"

    answer, _ = rag_system.query("What is RAG?")

    assert answer == "The answer"
    call_kwargs = rag_system.ai_generator.generate_response.call_args.kwargs
    assert call_kwargs["conversation_history"] is None
    assert call_kwargs["tool_manager"] is rag_system.tool_manager


def test_query_with_session_includes_conversation_history_and_updates_it(rag_system):
    rag_system.ai_generator.generate_response.return_value = "The answer"
    rag_system.session_manager.get_conversation_history = MagicMock(
        return_value="User: hi\nAssistant: hello"
    )
    rag_system.session_manager.add_exchange = MagicMock()

    rag_system.query("Follow up question", session_id="session_1")

    call_kwargs = rag_system.ai_generator.generate_response.call_args.kwargs
    assert call_kwargs["conversation_history"] == "User: hi\nAssistant: hello"
    rag_system.session_manager.add_exchange.assert_called_once_with(
        "session_1", "Follow up question", "The answer"
    )


def test_query_returns_and_resets_tool_sources(rag_system):
    rag_system.ai_generator.generate_response.return_value = "Answer"
    rag_system.tool_manager.get_last_sources = MagicMock(
        return_value=[{"text": "Course A", "link": None}]
    )
    rag_system.tool_manager.reset_sources = MagicMock()

    _, sources = rag_system.query("question")

    assert sources == [{"text": "Course A", "link": None}]
    rag_system.tool_manager.reset_sources.assert_called_once()


def test_get_course_analytics_reads_vector_store(rag_system):
    rag_system.vector_store.get_course_count.return_value = 3
    rag_system.vector_store.get_existing_course_titles.return_value = ["A", "B", "C"]

    analytics = rag_system.get_course_analytics()

    assert analytics == {"total_courses": 3, "course_titles": ["A", "B", "C"]}


def test_add_course_document_adds_to_vector_store(rag_system):
    course = Course(title="Course A")
    chunks = [CourseChunk(content="text", course_title="Course A", chunk_index=0)]
    rag_system.document_processor.process_course_document = MagicMock(return_value=(course, chunks))

    result_course, chunk_count = rag_system.add_course_document("some/path.txt")

    assert result_course is course
    assert chunk_count == 1
    rag_system.vector_store.add_course_metadata.assert_called_once_with(course)
    rag_system.vector_store.add_course_content.assert_called_once_with(chunks)


def test_add_course_document_returns_none_on_error(rag_system):
    rag_system.document_processor.process_course_document = MagicMock(
        side_effect=RuntimeError("bad file")
    )

    result_course, chunk_count = rag_system.add_course_document("bad/path.txt")

    assert result_course is None
    assert chunk_count == 0


def test_add_course_folder_skips_existing_courses(rag_system, tmp_path):
    (tmp_path / "course.txt").write_text("dummy", encoding="utf-8")
    existing_course = Course(title="Existing Course")
    rag_system.vector_store.get_existing_course_titles.return_value = ["Existing Course"]
    rag_system.document_processor.process_course_document = MagicMock(
        return_value=(existing_course, [])
    )

    total_courses, total_chunks = rag_system.add_course_folder(str(tmp_path))

    assert (total_courses, total_chunks) == (0, 0)
    rag_system.vector_store.add_course_metadata.assert_not_called()


def test_add_course_folder_adds_new_courses(rag_system, tmp_path):
    (tmp_path / "course.txt").write_text("dummy", encoding="utf-8")
    new_course = Course(title="New Course")
    chunks = [CourseChunk(content="text", course_title="New Course", chunk_index=0)]
    rag_system.vector_store.get_existing_course_titles.return_value = []
    rag_system.document_processor.process_course_document = MagicMock(
        return_value=(new_course, chunks)
    )

    total_courses, total_chunks = rag_system.add_course_folder(str(tmp_path))

    assert (total_courses, total_chunks) == (1, 1)
    rag_system.vector_store.add_course_metadata.assert_called_once_with(new_course)


def test_add_course_folder_returns_zero_for_missing_folder(rag_system):
    total_courses, total_chunks = rag_system.add_course_folder("/nonexistent/path")
    assert (total_courses, total_chunks) == (0, 0)


def test_add_course_folder_clears_data_when_requested(rag_system, tmp_path):
    rag_system.vector_store.get_existing_course_titles.return_value = []

    rag_system.add_course_folder(str(tmp_path), clear_existing=True)

    rag_system.vector_store.clear_all_data.assert_called_once()
