import logging

from telegram import Update

from database.queries import get_or_create_user

logger = logging.getLogger(__name__)


class AuthMiddleware:
    @staticmethod
    async def process(update: Update) -> tuple[bool, dict | None]:
        """Returns (is_allowed, user_data)"""
        if not update.effective_user:
            return False, None

        tg_user = update.effective_user
        user = await get_or_create_user(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )

        if user.get("is_banned"):
            logger.warning(f"Banned user attempt: {tg_user.id}")
            return False, None

        return True, user
