from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import BigInteger, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tezmafia.engine import Game, from_dict, to_dict
from tezmafia.shop import ITEMS, PLAY_COINS, ROLE_TICKET_COST, WIN_COINS, WIN_GEMS, empty_flags


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0)


class UserStat(Base):
    __tablename__ = "stats"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    games: Mapped[int] = mapped_column(Integer, default=0)
    wins: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    gems: Mapped[int] = mapped_column(Integer, default=0)
    inventory: Mapped[str] = mapped_column(Text, default="{}")
    next_role: Mapped[str] = mapped_column(String(32), default="")


class ChatPref(Base):
    __tablename__ = "prefs"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), default="uz")


class Store:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite"):
            Path("data").mkdir(exist_ok=True)
        self.engine = create_async_engine(url, echo=False)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for ddl in (
                "ALTER TABLE stats ADD COLUMN coins INTEGER DEFAULT 0",
                "ALTER TABLE stats ADD COLUMN gems INTEGER DEFAULT 0",
                "ALTER TABLE stats ADD COLUMN inventory TEXT DEFAULT '{}'",
                "ALTER TABLE stats ADD COLUMN next_role VARCHAR(32) DEFAULT ''",
            ):
                try:
                    await conn.execute(text(ddl))
                except Exception:
                    pass

    async def save(self, game: Game) -> None:
        async with self.session() as s:
            row = await s.get(GameRow, game.id)
            payload = json.dumps(to_dict(game), ensure_ascii=False)
            if row is None:
                s.add(
                    GameRow(
                        id=game.id,
                        chat_id=game.chat_id,
                        status=game.phase,
                        payload=payload,
                        version=game.version,
                    )
                )
            else:
                row.chat_id = game.chat_id
                row.status = game.phase
                row.payload = payload
                row.version = game.version
            await s.commit()

    async def load(self, game_id: str) -> Game | None:
        async with self.session() as s:
            row = await s.get(GameRow, game_id)
            if not row:
                return None
            return from_dict(json.loads(row.payload))

    async def active_in_chat(self, chat_id: int) -> Game | None:
        async with self.session() as s:
            q = await s.execute(
                select(GameRow)
                .where(GameRow.chat_id == chat_id, GameRow.status != "finished")
                .order_by(GameRow.version.desc())
            )
            row = q.scalars().first()
            if not row:
                return None
            return from_dict(json.loads(row.payload))

    async def by_user_lobby_or_live(self, user_id: int) -> Game | None:
        async with self.session() as s:
            q = await s.execute(select(GameRow).where(GameRow.status != "finished"))
            for row in q.scalars():
                game = from_dict(json.loads(row.payload))
                if game.by_user(user_id):
                    return game
        return None

    async def unfinished(self) -> list[Game]:
        async with self.session() as s:
            q = await s.execute(select(GameRow).where(GameRow.status != "finished"))
            return [from_dict(json.loads(r.payload)) for r in q.scalars()]

    async def bump_stat(self, user_id: int, name: str, won: bool) -> None:
        coins = PLAY_COINS + (WIN_COINS if won else 0)
        gems = WIN_GEMS if won else 0
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if row is None:
                s.add(
                    UserStat(
                        user_id=user_id,
                        name=name[:128],
                        games=1,
                        wins=1 if won else 0,
                        coins=coins,
                        gems=gems,
                        inventory="{}",
                    )
                )
            else:
                row.name = name[:128]
                row.games += 1
                if won:
                    row.wins += 1
                row.coins = (row.coins or 0) + coins
                row.gems = (row.gems or 0) + gems
            await s.commit()

    async def get_stat(self, user_id: int) -> tuple[str, int, int]:
        acc = await self.get_account(user_id)
        return (acc["name"], acc["games"], acc["wins"])

    async def get_account(self, user_id: int) -> dict:
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if not row:
                return {
                    "name": "",
                    "games": 0,
                    "wins": 0,
                    "coins": 0,
                    "gems": 0,
                    "inventory": {},
                    "next_role": "",
                }
            try:
                inv = json.loads(row.inventory or "{}")
            except json.JSONDecodeError:
                inv = {}
            if not isinstance(inv, dict):
                inv = {}
            return {
                "name": row.name,
                "games": row.games,
                "wins": row.wins,
                "coins": row.coins or 0,
                "gems": row.gems or 0,
                "inventory": {str(k): int(v) for k, v in inv.items() if int(v) > 0},
                "next_role": row.next_role or "",
            }

    async def credit_wallet(self, user_id: int, name: str, coins: int = 0, gems: int = 0) -> None:
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if row is None:
                s.add(
                    UserStat(
                        user_id=user_id,
                        name=name[:128],
                        coins=max(0, coins),
                        gems=max(0, gems),
                        inventory="{}",
                    )
                )
            else:
                row.name = name[:128]
                row.coins = (row.coins or 0) + coins
                row.gems = (row.gems or 0) + gems
            await s.commit()

    async def buy_item(self, user_id: int, name: str, item_key: str) -> tuple[bool, str]:
        if item_key not in ITEMS:
            return False, "no_item"
        cost = int(ITEMS[item_key]["cost"])
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if row is None:
                s.add(UserStat(user_id=user_id, name=name[:128], inventory="{}"))
                await s.commit()
                return False, "no_money"
            if (row.coins or 0) < cost:
                return False, "no_money"
            try:
                inv = json.loads(row.inventory or "{}")
            except json.JSONDecodeError:
                inv = {}
            if not isinstance(inv, dict):
                inv = {}
            row.coins = (row.coins or 0) - cost
            inv[item_key] = int(inv.get(item_key, 0)) + 1
            row.inventory = json.dumps(inv, ensure_ascii=False)
            row.name = name[:128]
            await s.commit()
        return True, "ok"

    async def take_loadout(self, user_id: int, skip: set[str] | None = None) -> dict[str, bool]:
        flags = empty_flags()
        skip = skip or set()
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if not row:
                return flags
            try:
                inv = json.loads(row.inventory or "{}")
            except json.JSONDecodeError:
                inv = {}
            if not isinstance(inv, dict):
                inv = {}
            changed = False
            for key in ITEMS:
                if key in skip:
                    continue
                count = int(inv.get(key, 0) or 0)
                if count > 0:
                    flags[key] = True
                    inv[key] = count - 1
                    if inv[key] <= 0:
                        inv.pop(key, None)
                    changed = True
            if changed:
                row.inventory = json.dumps(inv, ensure_ascii=False)
                await s.commit()
        return flags

    async def buy_next_role(self, user_id: int, name: str, role: str) -> tuple[bool, str]:
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if row is None:
                s.add(UserStat(user_id=user_id, name=name[:128], inventory="{}"))
                await s.commit()
                return False, "no_money"
            if (row.next_role or "").strip():
                return False, "already_queued"
            if (row.coins or 0) < ROLE_TICKET_COST:
                return False, "no_money"
            row.coins = (row.coins or 0) - ROLE_TICKET_COST
            row.next_role = role
            row.name = name[:128]
            await s.commit()
        return True, "ok"

    async def take_next_role(self, user_id: int) -> str:
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if not row or not (row.next_role or "").strip():
                return ""
            role = row.next_role
            row.next_role = ""
            await s.commit()
            return role

    async def top_stats(self, limit: int = 10) -> list[tuple[str, int, int]]:
        async with self.session() as s:
            q = await s.execute(select(UserStat).order_by(UserStat.wins.desc(), UserStat.games.desc()).limit(limit))
            return [(r.name or str(r.user_id), r.games, r.wins) for r in q.scalars()]

    async def get_lang(self, chat_id: int) -> str:
        async with self.session() as s:
            row = await s.get(ChatPref, chat_id)
            return row.lang if row else "uz"

    async def games_for_user(self, user_id: int) -> list[Game]:
        found: list[Game] = []
        for game in await self.unfinished():
            if game.by_user(user_id):
                found.append(game)
        return found

    async def set_lang(self, chat_id: int, lang: str) -> str:
        from tezmafia.i18n import normalize_lang

        lang = normalize_lang(lang)
        async with self.session() as s:
            row = await s.get(ChatPref, chat_id)
            if row is None:
                s.add(ChatPref(chat_id=chat_id, lang=lang))
            else:
                row.lang = lang
            await s.commit()
        return lang
