"""Fallback chain: Claude → GPT-4o → Gemini"""

import logging

from solvers.base import BaseSolver, SolverResult
from solvers.claude import ClaudeSolver

logger = logging.getLogger(__name__)


class FallbackSolver(BaseSolver):
    def __init__(self):
        self._solvers: list[BaseSolver] = [ClaudeSolver()]
        self._try_optional_solvers()

    def _try_optional_solvers(self):
        from config import get_settings

        s = get_settings()

        if s.openai_api_key:
            try:
                from solvers.gpt4o import GPT4oSolver

                self._solvers.append(GPT4oSolver())
            except ImportError:
                logger.warning("openai package not installed, GPT-4o fallback disabled")

        if s.gemini_api_key:
            try:
                from solvers.gemini import GeminiSolver

                self._solvers.append(GeminiSolver())
            except ImportError:
                logger.warning("google-generativeai not installed, Gemini fallback disabled")

    async def solve(
        self,
        problem_text: str,
        image_data: bytes | None = None,
        lang: str = "uz",
    ) -> SolverResult:
        last_error: Exception | None = None

        for solver in self._solvers:
            try:
                result = await solver.solve(problem_text, image_data, lang)
                return result
            except Exception as e:
                logger.warning(f"{solver.__class__.__name__} failed: {e}, trying next...")
                last_error = e

        raise RuntimeError(f"All solvers failed. Last error: {last_error}")
