import pytest
from ai_generator import AIGenerator
from search_tools import CourseSearchTool, ToolManager

from tests.helpers import make_text_response, make_tool_use_response


pytestmark = pytest.mark.unit


def test_generate_response_without_tools_returns_direct_text(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = make_text_response("Paris is the capital of France.")

    generator = AIGenerator(api_key="fake-key", model="claude-test-model")
    result = generator.generate_response(query="What is the capital of France?")

    assert result == "Paris is the capital of France."
    mock_anthropic_client.messages.create.assert_called_once()
    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs


def test_generate_response_includes_history_in_system_prompt(mock_anthropic_client):
    mock_anthropic_client.messages.create.return_value = make_text_response("Sure, following up...")

    generator = AIGenerator(api_key="fake-key", model="claude-test-model")
    generator.generate_response(query="Tell me more", conversation_history="User: Hi\nAssistant: Hello!")

    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert "Previous conversation" in call_kwargs["system"]
    assert "User: Hi" in call_kwargs["system"]


def test_generate_response_invokes_tool_and_returns_followup_text(mock_anthropic_client, mock_vector_store):
    tool_manager = ToolManager()
    tool_manager.register_tool(CourseSearchTool(mock_vector_store))

    mock_anthropic_client.messages.create.side_effect = [
        make_tool_use_response("search_course_content", {"query": "what is RAG?"}),
        make_text_response("RAG combines retrieval with generation."),
    ]

    generator = AIGenerator(api_key="fake-key", model="claude-test-model")
    result = generator.generate_response(
        query="What is RAG?",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager,
    )

    assert result == "RAG combines retrieval with generation."
    assert mock_anthropic_client.messages.create.call_count == 2
    mock_vector_store.search.assert_called_once()


def test_generate_response_second_call_omits_tools(mock_anthropic_client, mock_vector_store):
    tool_manager = ToolManager()
    tool_manager.register_tool(CourseSearchTool(mock_vector_store))

    mock_anthropic_client.messages.create.side_effect = [
        make_tool_use_response("search_course_content", {"query": "what is RAG?"}),
        make_text_response("Final answer."),
    ]

    generator = AIGenerator(api_key="fake-key", model="claude-test-model")
    generator.generate_response(
        query="What is RAG?",
        tools=tool_manager.get_tool_definitions(),
        tool_manager=tool_manager,
    )

    second_call_kwargs = mock_anthropic_client.messages.create.call_args_list[1].kwargs
    assert "tools" not in second_call_kwargs
