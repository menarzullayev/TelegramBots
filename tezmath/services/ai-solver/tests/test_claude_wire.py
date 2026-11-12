"""Run the real anthropic SDK client against a mock HTTP transport (request and response parsing)."""

import json

import anthropic
import httpx2
import pytest


@pytest.mark.asyncio
async def test_claude_solver_wire_format_against_real_sdk_client():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{"type": "text", "text": "Yechim: $$x = 5$$"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 11, "output_tokens": 22},
            },
        )

    from solvers.claude import MODEL, ClaudeSolver

    solver = ClaudeSolver()
    solver._client = anthropic.AsyncAnthropic(
        api_key="test-key", http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    )
    result = await solver.solve("x + 3 = 8", lang="uz")

    assert seen["path"] == "/v1/messages"
    assert seen["body"]["model"] == MODEL
    assert seen["body"]["messages"][0]["role"] == "user"
    assert result.tokens_used == 33
    assert result.latex_source == "x = 5"
