import pytest

from app.api.chat import RuntimeServices, _message_text
from app.config import Settings


def test_runtime_requires_anthropic_key() -> None:
    settings = Settings(anthropic_api_key=None)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        RuntimeServices(settings=settings)


def test_runtime_uses_configured_retrieval_distance() -> None:
    settings = Settings(
        anthropic_api_key="test-key",
        retrieval_max_distance=0.72,
    )

    services = RuntimeServices(settings=settings)

    assert services.max_distance == 0.72


def test_message_text_keeps_plain_string() -> None:
    assert _message_text("直接文本") == "直接文本"


def test_message_text_extracts_anthropic_text_blocks() -> None:
    content = [
        {"type": "text", "text": "第一段"},
        {"type": "tool_use", "name": "ignored"},
        {"type": "text", "text": "第二段"},
    ]

    assert _message_text(content) == "第一段\n第二段"
