import json
from unittest.mock import MagicMock, patch

import pytest

from models import Course, CourseChunk, Lesson
from vector_store import SearchResults, VectorStore


pytestmark = pytest.mark.unit


class TestSearchResults:
    def test_from_chroma_builds_results_from_chroma_response(self):
        chroma_response = {
            "documents": [["doc one", "doc two"]],
            "metadatas": [[{"course_title": "A"}, {"course_title": "B"}]],
            "distances": [[0.1, 0.2]],
        }
        results = SearchResults.from_chroma(chroma_response)

        assert results.documents == ["doc one", "doc two"]
        assert results.metadata[0]["course_title"] == "A"
        assert results.distances == [0.1, 0.2]
        assert results.error is None

    def test_from_chroma_handles_empty_documents(self):
        chroma_response = {"documents": [], "metadatas": [], "distances": []}
        results = SearchResults.from_chroma(chroma_response)
        assert results.is_empty()

    def test_empty_sets_error_message(self):
        results = SearchResults.empty("boom")
        assert results.error == "boom"
        assert results.is_empty()


@pytest.fixture
def vector_store():
    with patch("vector_store.chromadb.PersistentClient") as mock_client_cls, patch(
        "vector_store.chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction"
    ):
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.get_or_create_collection.side_effect = lambda *args, **kwargs: MagicMock()

        store = VectorStore(chroma_path="/tmp/fake_chroma", embedding_model="fake-model", max_results=5)
        yield store


def test_build_filter_with_no_filters_returns_none(vector_store):
    assert vector_store._build_filter(None, None) is None


def test_build_filter_with_course_only(vector_store):
    assert vector_store._build_filter("Course A", None) == {"course_title": "Course A"}


def test_build_filter_with_lesson_only(vector_store):
    assert vector_store._build_filter(None, 3) == {"lesson_number": 3}


def test_build_filter_with_course_and_lesson(vector_store):
    result = vector_store._build_filter("Course A", 3)
    assert result == {"$and": [{"course_title": "Course A"}, {"lesson_number": 3}]}


def test_search_resolves_course_name_and_queries_content(vector_store):
    vector_store.course_catalog.query.return_value = {
        "documents": [["Course A"]],
        "metadatas": [[{"title": "Course A"}]],
    }
    vector_store.course_content.query.return_value = {
        "documents": [["chunk text"]],
        "metadatas": [[{"course_title": "Course A", "lesson_number": 1}]],
        "distances": [[0.05]],
    }

    results = vector_store.search(query="topic", course_name="course a")

    vector_store.course_catalog.query.assert_called_once_with(query_texts=["course a"], n_results=1)
    vector_store.course_content.query.assert_called_once_with(
        query_texts=["topic"], n_results=5, where={"course_title": "Course A"}
    )
    assert results.documents == ["chunk text"]


def test_search_returns_error_when_course_name_not_found(vector_store):
    vector_store.course_catalog.query.return_value = {"documents": [[]], "metadatas": [[]]}

    results = vector_store.search(query="topic", course_name="Unknown Course")

    assert results.error == "No course found matching 'Unknown Course'"
    vector_store.course_content.query.assert_not_called()


def test_search_wraps_exceptions_as_error_result(vector_store):
    vector_store.course_content.query.side_effect = RuntimeError("boom")

    results = vector_store.search(query="topic")
    assert results.error == "Search error: boom"


def test_add_course_metadata_serializes_lessons_as_json(vector_store):
    course = Course(
        title="Course A",
        course_link="https://example.com",
        instructor="Jane",
        lessons=[Lesson(lesson_number=1, title="Intro", lesson_link="https://example.com/l1")],
    )
    vector_store.add_course_metadata(course)

    call_kwargs = vector_store.course_catalog.add.call_args.kwargs
    assert call_kwargs["ids"] == ["Course A"]
    metadata = call_kwargs["metadatas"][0]
    assert metadata["title"] == "Course A"
    lessons = json.loads(metadata["lessons_json"])
    assert lessons[0]["lesson_number"] == 1


def test_add_course_content_builds_ids_from_title_and_chunk_index(vector_store):
    chunks = [
        CourseChunk(content="text one", course_title="Course A", lesson_number=1, chunk_index=0),
        CourseChunk(content="text two", course_title="Course A", lesson_number=1, chunk_index=1),
    ]
    vector_store.add_course_content(chunks)

    call_kwargs = vector_store.course_content.add.call_args.kwargs
    assert call_kwargs["ids"] == ["Course_A_0", "Course_A_1"]
    assert call_kwargs["documents"] == ["text one", "text two"]


def test_add_course_content_noop_for_empty_chunks(vector_store):
    vector_store.add_course_content([])
    vector_store.course_content.add.assert_not_called()


def test_get_lesson_link_parses_lessons_json(vector_store):
    vector_store.course_catalog.get.return_value = {
        "metadatas": [{"lessons_json": json.dumps([{"lesson_number": 2, "lesson_link": "https://x/l2"}])}]
    }
    link = vector_store.get_lesson_link("Course A", 2)
    assert link == "https://x/l2"


def test_get_course_count_reads_catalog_ids(vector_store):
    vector_store.course_catalog.get.return_value = {"ids": ["Course A", "Course B"]}
    assert vector_store.get_course_count() == 2
