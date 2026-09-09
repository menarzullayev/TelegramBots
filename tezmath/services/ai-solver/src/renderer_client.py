import logging

import httpx

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def render_latex(latex_source: str) -> str | None:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.renderer_url}/render",
                json={"latex": latex_source},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("url")
    except Exception as e:
        logger.warning(f"Renderer error: {e}")
        return None
