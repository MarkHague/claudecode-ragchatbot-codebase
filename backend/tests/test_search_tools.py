import pytest
from search_tools import CourseSearchTool, ToolManager
from vector_store import SearchResults


pytestmark = pytest.mark.unit


def test_get_tool_definition_has_expected_shape(mock_vector_store):
    tool = CourseSearchTool(mock_vector_store)
    definition = tool.get_tool_definition()

    assert definition["name"] == "search_course_content"
    assert "query" in definition["input_schema"]["properties"]
    assert definition["input_schema"]["required"] == ["query"]


def test_execute_returns_formatted_results_with_lesson_header(mock_vector_store, sample_course):
    tool = CourseSearchTool(mock_vector_store)
    result = tool.execute(query="what is RAG?")

    mock_vector_store.search.assert_called_once_with(
        query="what is RAG?", course_name=None, lesson_number=None
    )
    assert f"[{sample_course.title} - Lesson 1]" in result
    assert "introduction to RAG systems" in result


def test_execute_passes_course_and_lesson_filters(mock_vector_store):
    tool = CourseSearchTool(mock_vector_store)
    tool.execute(query="topic", course_name="RAG Systems", lesson_number=2)

    mock_vector_store.search.assert_called_once_with(
        query="topic", course_name="RAG Systems", lesson_number=2
    )


def test_execute_tracks_sources_after_search(mock_vector_store, sample_course):
    tool = CourseSearchTool(mock_vector_store)
    tool.execute(query="what is RAG?")

    assert tool.last_sources == [
        {"text": f"{sample_course.title} - Lesson 1", "link": "https://example.com/lesson1"}
    ]


def test_execute_returns_error_message_when_store_errors(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults.empty("No course found matching 'Bogus'")
    tool = CourseSearchTool(mock_vector_store)

    result = tool.execute(query="anything", course_name="Bogus")
    assert result == "No course found matching 'Bogus'"


def test_execute_returns_no_results_message_when_empty(mock_vector_store):
    mock_vector_store.search.return_value = SearchResults(documents=[], metadata=[], distances=[])
    tool = CourseSearchTool(mock_vector_store)

    result = tool.execute(query="anything", course_name="Some Course", lesson_number=3)
    assert result == "No relevant content found in course 'Some Course' in lesson 3."


class TestToolManager:
    def test_register_tool_and_get_definitions(self, mock_vector_store):
        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        definitions = manager.get_tool_definitions()
        assert len(definitions) == 1
        assert definitions[0]["name"] == "search_course_content"

    def test_execute_tool_by_name(self, mock_vector_store):
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))

        result = manager.execute_tool("search_course_content", query="what is RAG?")
        assert "introduction to RAG systems" in result

    def test_execute_unknown_tool_returns_error_string(self):
        manager = ToolManager()
        result = manager.execute_tool("nonexistent_tool", query="x")
        assert result == "Tool 'nonexistent_tool' not found"

    def test_get_last_sources_and_reset(self, mock_vector_store):
        manager = ToolManager()
        manager.register_tool(CourseSearchTool(mock_vector_store))
        manager.execute_tool("search_course_content", query="what is RAG?")

        assert manager.get_last_sources() != []
        manager.reset_sources()
        assert manager.get_last_sources() == []
