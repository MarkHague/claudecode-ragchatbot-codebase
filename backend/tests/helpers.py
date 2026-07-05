"""Small builders for mock Anthropic API responses, shared across test modules."""
from unittest.mock import MagicMock


def make_text_response(text: str):
    """Builds a mock Anthropic response with stop_reason == 'end_turn'."""
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [MagicMock(text=text)]
    return response


def make_tool_use_response(tool_name: str, tool_input: dict, tool_id: str = "tool_1"):
    """Builds a mock Anthropic response with stop_reason == 'tool_use'."""
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.input = tool_input
    block.id = tool_id

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [block]
    return response
