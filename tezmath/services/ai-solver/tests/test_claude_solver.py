from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_claude_solver_returns_result():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="**Javob:** $x = 5$")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 200

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        instance = mock_anthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from solvers.claude import ClaudeSolver

        solver = ClaudeSolver()
        result = await solver.solve("x + 3 = 8", lang="uz")

        assert "Javob" in result.solution_text
        assert result.tokens_used == 300
        assert result.model_used == "claude-sonnet-4-6"


@pytest.mark.asyncio
async def test_claude_solver_with_image():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="**Javob:** $y = 2$")]
    mock_response.usage.input_tokens = 500
    mock_response.usage.output_tokens = 300

    with patch("anthropic.AsyncAnthropic") as mock_anthropic:
        instance = mock_anthropic.return_value
        instance.messages.create = AsyncMock(return_value=mock_response)

        from solvers.claude import ClaudeSolver

        solver = ClaudeSolver()
        result = await solver.solve("", image_data=b"fake_image_data", lang="ru")

        assert result.solution_text != ""
        call_args = instance.messages.create.call_args
        messages = call_args.kwargs["messages"]
        assert messages[0]["content"][0]["type"] == "image"
