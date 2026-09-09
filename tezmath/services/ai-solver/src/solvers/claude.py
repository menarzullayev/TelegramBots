import base64
import logging

import anthropic
from solvers.base import BaseSolver, SolverResult
from solvers.prompts import build_system_prompt, build_user_message

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"


class ClaudeSolver(BaseSolver):
    def __init__(self):
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def solve(
        self,
        problem_text: str,
        image_data: bytes | None = None,
        lang: str = "uz",
    ) -> SolverResult:
        messages = self._build_messages(problem_text, image_data)

        response = await self._client.messages.create(
            model=MODEL,
            max_tokens=settings.max_tokens,
            system=build_system_prompt(lang),
            messages=messages,
        )

        solution_text = response.content[0].text
        tokens = response.usage.input_tokens + response.usage.output_tokens

        latex_source = self._extract_latex(solution_text)

        logger.info(f"Claude solved: {tokens} tokens, lang={lang}")

        return SolverResult(
            solution_text=solution_text,
            latex_source=latex_source,
            model_used=MODEL,
            tokens_used=tokens,
        )

    def _build_messages(self, problem_text: str, image_data: bytes | None) -> list:
        content: list = []

        if image_data:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(image_data).decode(),
                    },
                }
            )

        user_text = build_user_message(problem_text, has_image=image_data is not None)
        content.append({"type": "text", "text": user_text})

        return [{"role": "user", "content": content}]

    def _extract_latex(self, text: str) -> str | None:
        import re

        blocks = re.findall(r"\$\$(.*?)\$\$", text, re.DOTALL)
        return "\n\n".join(blocks) if blocks else None
