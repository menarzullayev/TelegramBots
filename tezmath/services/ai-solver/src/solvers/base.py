from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SolverResult:
    solution_text: str
    latex_source: str | None = None
    steps: list[str] | None = None
    model_used: str = ""
    tokens_used: int = 0


class BaseSolver(ABC):
    @abstractmethod
    async def solve(
        self,
        problem_text: str,
        image_data: bytes | None = None,
        lang: str = "uz",
    ) -> SolverResult: ...
