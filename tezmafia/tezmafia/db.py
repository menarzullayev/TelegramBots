from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import BigInteger, Float, Integer, String, Text, delete, event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from tezmafia.engine import Game, from_dict, to_dict
from tezmafia.shop import (
    BADGES,
    ITEMS,
    PLAY_COINS,
    ROLE_TICKET_COST,
    SPECIAL_BADGES,
    VIP_BADGE,
    VIP_COIN_BONUS,
    WIN_COINS,
    WIN_GEMS,
    empty_flags,
)


class Base(DeclarativeBase):
    pass


class GameRow(Base):
    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float | None] = mapped_column(Float, default=time.time, nullable=True)
    updated_at: Mapped[float | None] = mapped_column(Float, default=time.time, nullable=True, index=True)


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
    first_seen: Mapped[float | None] = mapped_column(Float, default=time.time, nullable=True)
    vip_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    badge: Mapped[str] = mapped_column(String(16), default="")
    badges: Mapped[str] = mapped_column(Text, default="[]")
    xp: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    daily_last: Mapped[str] = mapped_column(String(10), default="", server_default="")
    daily_streak: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Clan(Base):
    __tablename__ = "clans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32))
    name_key: Mapped[str] = mapped_column(String(32), unique=True)
    owner_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[float] = mapped_column(Float, default=time.time)


class ClanMember(Base):
    __tablename__ = "clan_members"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    clan_id: Mapped[int] = mapped_column(Integer, index=True)
    joined_at: Mapped[float] = mapped_column(Float, default=time.time)


class WeeklyStat(Base):
    __tablename__ = "weekly_stats"

    week: Mapped[str] = mapped_column(String(8), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    games: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class TournamentAward(Base):
    __tablename__ = "tournament_awards"

    week: Mapped[str] = mapped_column(String(8), primary_key=True)
    at: Mapped[float] = mapped_column(Float, default=time.time)


class LastCard(Base):
    """The player's latest result card (Telegram file id) for inline sharing."""

    __tablename__ = "last_cards"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    file_id: Mapped[str] = mapped_column(String(256))
    caption: Mapped[str] = mapped_column(Text, default="")


class QuestProgress(Base):
    __tablename__ = "quest_progress"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    done: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Referral(Base):
    __tablename__ = "referrals"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, index=True)
    at: Mapped[float] = mapped_column(Float, default=time.time)
    rewarded: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    at: Mapped[float] = mapped_column(Float)
    created_by: Mapped[int] = mapped_column(BigInteger)
    creator_name: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(12), default="pending", server_default="pending")


class ScheduleSub(Base):
    __tablename__ = "schedule_subs"

    schedule_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class SeasonStat(Base):
    """Monthly ranking rows; chat_id 0 is the global ladder, other ids are per-group ladders."""

    __tablename__ = "season_stats"

    season: Mapped[str] = mapped_column(String(7), primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), default="")
    games: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    wins: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Achievement(Base):
    __tablename__ = "achievements"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    at: Mapped[float] = mapped_column(Float, default=time.time)


class Payment(Base):
    """Telegram Stars ledger. charge_id is Telegram's id, so a replayed update is never credited twice."""

    __tablename__ = "payments"

    charge_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    product: Mapped[str] = mapped_column(String(16))
    stars: Mapped[int] = mapped_column(Integer)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[float] = mapped_column(Float, default=time.time, index=True)
    refunded_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class Activity(Base):
    """One row per user, day and channel ("dm" / "group"): the bot's own DAU/MAU source."""

    __tablename__ = "activity"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    channel: Mapped[str] = mapped_column(String(8), primary_key=True)


class ChatSettings(Base):
    """Per-group /config choices as JSON; missing keys fall back to the bot-wide defaults."""

    __tablename__ = "chat_settings"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    data: Mapped[str] = mapped_column(Text, default="{}")


class ChatPref(Base):
    __tablename__ = "prefs"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    lang: Mapped[str] = mapped_column(String(8), default="uz")


def _sqlite_pragmas(dbapi_conn, _record) -> None:
    # busy_timeout makes a writer wait for another chat's write instead of failing with "database is locked".
    # No WAL: the file is shared between Windows and Linux boots on NTFS, and a plain file copy must stay a backup.
    cur = dbapi_conn.cursor()
    for pragma in ("busy_timeout=5000", "foreign_keys=ON"):
        cur.execute(f"PRAGMA {pragma}")
    cur.close()


class Store:
    def __init__(self, url: str) -> None:
        if url.startswith("sqlite"):
            Path("data").mkdir(exist_ok=True)
        self.engine = create_async_engine(url, echo=False)
        if url.startswith("sqlite"):
            event.listen(self.engine.sync_engine, "connect", _sqlite_pragmas)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            for ddl in (
                "ALTER TABLE stats ADD COLUMN coins INTEGER DEFAULT 0",
                "ALTER TABLE stats ADD COLUMN gems INTEGER DEFAULT 0",
                "ALTER TABLE stats ADD COLUMN inventory TEXT DEFAULT '{}'",
                "ALTER TABLE stats ADD COLUMN next_role VARCHAR(32) DEFAULT ''",
                "ALTER TABLE stats ADD COLUMN first_seen FLOAT",
                "ALTER TABLE stats ADD COLUMN vip_until FLOAT",
                "ALTER TABLE stats ADD COLUMN badge VARCHAR(16) DEFAULT ''",
                "ALTER TABLE stats ADD COLUMN badges TEXT DEFAULT '[]'",
                "ALTER TABLE stats ADD COLUMN xp INTEGER DEFAULT 0",
                "ALTER TABLE stats ADD COLUMN daily_last VARCHAR(10) DEFAULT ''",
                "ALTER TABLE stats ADD COLUMN daily_streak INTEGER DEFAULT 0",
                "ALTER TABLE games ADD COLUMN created_at FLOAT",
                "ALTER TABLE games ADD COLUMN updated_at FLOAT",
                "CREATE INDEX IF NOT EXISTS ix_games_updated_at ON games (updated_at)",
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
                row.updated_at = time.time()
            await s.commit()

    async def prune_activity(self, keep_days: int = 400) -> None:
        cutoff = time.strftime("%Y-%m-%d", time.localtime(time.time() - keep_days * 86400))
        async with self.session() as s:
            await s.execute(delete(Activity).where(Activity.day < cutoff))
            await s.commit()

    async def prune_finished(self, older_than_days: float) -> int:
        """Delete finished games last touched before the cutoff (rows without a timestamp are kept)."""
        cutoff = time.time() - older_than_days * 86400
        async with self.session() as s:
            res = await s.execute(
                delete(GameRow).where(GameRow.status == "finished", GameRow.updated_at.is_not(None), GameRow.updated_at < cutoff)
            )
            await s.commit()
            return res.rowcount or 0

    async def delete_user(self, user_id: int) -> dict[str, int]:
        """Erase a user's data: stats/wallet row, private-chat language, and their name in finished games.

        Unfinished games are left alone; callers refuse deletion while the user is still playing.
        """
        scrubbed = 0
        async with self.session() as s:
            stats = await s.execute(delete(UserStat).where(UserStat.user_id == user_id))
            prefs = await s.execute(delete(ChatPref).where(ChatPref.chat_id == user_id))
            await s.execute(delete(Activity).where(Activity.user_id == user_id))
            await s.execute(delete(Achievement).where(Achievement.user_id == user_id))
            await s.execute(delete(QuestProgress).where(QuestProgress.user_id == user_id))
            await s.execute(delete(WeeklyStat).where(WeeklyStat.user_id == user_id))
            await s.execute(delete(LastCard).where(LastCard.user_id == user_id))
            await s.execute(delete(ScheduleSub).where(ScheduleSub.user_id == user_id))
            await s.execute(delete(SeasonStat).where(SeasonStat.user_id == user_id))
            rows = (await s.execute(select(GameRow).where(GameRow.status == "finished"))).scalars().all()
            for row in rows:
                data = json.loads(row.payload)
                touched = False
                for player in data.get("players", []):
                    if player.get("user_id") == user_id and (player.get("first_name") != "—" or player.get("username")):
                        player["first_name"] = "—"
                        player["username"] = None
                        touched = True
                if touched:
                    row.payload = json.dumps(data, ensure_ascii=False)
                    scrubbed += 1
            await s.commit()
        return {"stats": stats.rowcount or 0, "prefs": prefs.rowcount or 0, "games": scrubbed}

    async def touch_activity(self, day: str, user_id: int, channel: str) -> None:
        async with self.session() as s:
            await s.execute(
                text("INSERT OR IGNORE INTO activity (day, user_id, channel) VALUES (:d, :u, :c)"),
                {"d": day, "u": user_id, "c": channel},
            )
            await s.commit()

    async def active_users(self, since_day: str, channel: str | None = None) -> int:
        """Distinct users active on or after since_day (YYYY-MM-DD), optionally in one channel."""
        q = select(func.count(func.distinct(Activity.user_id))).where(Activity.day >= since_day)
        if channel:
            q = q.where(Activity.channel == channel)
        async with self.session() as s:
            return (await s.execute(q)).scalar_one()

    async def report_since(self, since: float) -> dict[str, int]:
        """Counters for the owner's daily report."""
        async with self.session() as s:
            finished = (
                await s.execute(select(GameRow.payload).where(GameRow.status == "finished", GameRow.updated_at >= since))
            ).scalars().all()
            live = (await s.execute(select(func.count()).select_from(GameRow).where(GameRow.status != "finished"))).scalar_one()
            new_users = (await s.execute(select(func.count()).select_from(UserStat).where(UserStat.first_seen >= since))).scalar_one()
            users = (await s.execute(select(func.count()).select_from(UserStat))).scalar_one()
        players: set[int] = set()
        chats: set[int] = set()
        played = 0
        for payload in finished:
            game = from_dict(json.loads(payload))
            if game.winner:
                played += 1
            chats.add(game.chat_id)
            players.update(p.user_id for p in game.players)
        return {
            "games": played,
            "cancelled": len(finished) - played,
            "chats": len(chats),
            "players": len(players),
            "new_users": new_users,
            "users": users,
            "live": live,
        }

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

    async def _ensure(self, s: AsyncSession, user_id: int, name: str) -> None:
        await s.execute(
            text(
                "INSERT OR IGNORE INTO stats (user_id, name, games, wins, coins, gems, inventory, next_role, first_seen,"
                " badge, badges, xp, daily_last, daily_streak) VALUES (:u, :n, 0, 0, 0, 0, '{}', '', :t, '', '[]', 0, '', 0)"
            ),
            {"u": user_id, "n": name[:128], "t": time.time()},
        )

    async def bump_stat(self, user_id: int, name: str, won: bool, alive: bool = False) -> dict[str, int]:
        """Record one finished game; returns the totals after it (games, wins, xp)."""
        from tezmafia.progress import xp_for

        coins = PLAY_COINS + (WIN_COINS if won else 0)
        gems = WIN_GEMS if won else 0
        async with self.session() as s:
            await self._ensure(s, user_id, name)
            vip_until = (await s.execute(select(UserStat.vip_until).where(UserStat.user_id == user_id))).scalar()
            if vip_until and vip_until > time.time():
                coins += int(coins * VIP_COIN_BONUS)
            await s.execute(
                text(
                    "UPDATE stats SET name = :n, games = games + 1, wins = wins + :w, coins = COALESCE(coins, 0) + :c,"
                    " gems = COALESCE(gems, 0) + :g, xp = COALESCE(xp, 0) + :x WHERE user_id = :u"
                ),
                {"n": name[:128], "w": 1 if won else 0, "c": coins, "g": gems, "x": xp_for(won, alive), "u": user_id},
            )
            row = (
                await s.execute(select(UserStat.games, UserStat.wins, UserStat.xp).where(UserStat.user_id == user_id))
            ).one()
            await s.commit()
        return {"games": row[0], "wins": row[1], "xp": row[2] or 0}

    # --- retention: daily bonus, quests, referrals, schedules -------------------------------

    async def add_xp(self, user_id: int, xp: int) -> None:
        async with self.session() as s:
            await s.execute(text("UPDATE stats SET xp = COALESCE(xp, 0) + :x WHERE user_id = :u"), {"x": xp, "u": user_id})
            await s.commit()

    async def claim_daily(self, user_id: int, name: str, today: str, yesterday: str) -> dict[str, int] | None:
        """Give today's bonus once; None if it was already taken."""
        from tezmafia.retention import daily_reward, next_streak

        async with self.session() as s:
            await self._ensure(s, user_id, name)
            row = await s.get(UserStat, user_id)
            streak = next_streak(row.daily_last or "", today, yesterday, row.daily_streak or 0)
            if streak is None:
                return None
            coins, gems = daily_reward(streak)
            res = await s.execute(
                text(
                    "UPDATE stats SET daily_last = :d, daily_streak = :k, coins = COALESCE(coins, 0) + :c,"
                    " gems = COALESCE(gems, 0) + :g WHERE user_id = :u AND COALESCE(daily_last, '') != :d"
                ),
                {"d": today, "k": streak, "c": coins, "g": gems, "u": user_id},
            )
            await s.commit()
            if not res.rowcount:
                return None  # a parallel claim won
        return {"streak": streak, "coins": coins, "gems": gems}

    async def streaks_at_risk(self, yesterday: str, min_streak: int = 2) -> list[tuple[int, int]]:
        """Users who claimed yesterday (streak >= min) and not yet today."""
        async with self.session() as s:
            q = await s.execute(
                select(UserStat.user_id, UserStat.daily_streak).where(
                    UserStat.daily_last == yesterday, UserStat.daily_streak >= min_streak
                )
            )
            return [(r[0], r[1]) for r in q.all()]

    async def quest_advance(self, day: str, user_id: int, steps: dict[str, int]) -> list[str]:
        """Add progress; returns quests that became complete with this call."""
        from tezmafia.retention import QUESTS

        finished: list[str] = []
        async with self.session() as s:
            for key, inc in steps.items():
                target = QUESTS[key][0]
                row = await s.get(QuestProgress, (day, user_id, key))
                if row is None:
                    row = QuestProgress(day=day, user_id=user_id, key=key, progress=0, done=0)
                    s.add(row)
                if row.done:
                    continue
                row.progress = min(target, (row.progress or 0) + inc)
                if row.progress >= target:
                    row.done = 1
                    finished.append(key)
            await s.commit()
        return finished

    async def quest_state(self, day: str, user_id: int) -> dict[str, tuple[int, bool]]:
        async with self.session() as s:
            q = await s.execute(select(QuestProgress).where(QuestProgress.day == day, QuestProgress.user_id == user_id))
            return {r.key: (r.progress or 0, bool(r.done)) for r in q.scalars()}

    async def add_referral(self, user_id: int, referrer_id: int) -> bool:
        """Only brand-new users (no stats row, never referred) can be referred, and not by themselves."""
        if user_id == referrer_id:
            return False
        async with self.session() as s:
            if await s.get(UserStat, user_id) is not None or await s.get(Referral, user_id) is not None:
                return False
            s.add(Referral(user_id=user_id, referrer_id=referrer_id, at=time.time(), rewarded=0))
            await s.commit()
        return True

    async def take_referral(self, user_id: int) -> int | None:
        """Referrer id the first time this referred user is rewarded; None otherwise."""
        async with self.session() as s:
            res = await s.execute(
                text("UPDATE referrals SET rewarded = 1 WHERE user_id = :u AND rewarded = 0"), {"u": user_id}
            )
            if not res.rowcount:
                return None
            ref = await s.get(Referral, user_id)
            await s.commit()
            return ref.referrer_id if ref else None

    async def referral_count(self, referrer_id: int) -> int:
        async with self.session() as s:
            return (
                await s.execute(select(func.count()).select_from(Referral).where(Referral.referrer_id == referrer_id))
            ).scalar_one()

    async def create_schedule(self, chat_id: int, at: float, created_by: int, name: str) -> int:
        async with self.session() as s:
            await s.execute(
                text("UPDATE schedules SET state = 'cancelled' WHERE chat_id = :c AND state IN ('pending', 'notified')"),
                {"c": chat_id},
            )
            row = Schedule(chat_id=chat_id, at=at, created_by=created_by, creator_name=name[:128], state="pending")
            s.add(row)
            await s.commit()
            return row.id

    async def cancel_schedule(self, chat_id: int) -> bool:
        async with self.session() as s:
            res = await s.execute(
                text("UPDATE schedules SET state = 'cancelled' WHERE chat_id = :c AND state IN ('pending', 'notified')"),
                {"c": chat_id},
            )
            await s.commit()
            return bool(res.rowcount)

    async def subscribe(self, schedule_id: int, user_id: int) -> bool:
        async with self.session() as s:
            row = await s.get(Schedule, schedule_id)
            if not row or row.state not in ("pending", "notified"):
                return False
            await s.execute(
                text("INSERT OR IGNORE INTO schedule_subs (schedule_id, user_id) VALUES (:s, :u)"),
                {"s": schedule_id, "u": user_id},
            )
            await s.commit()
        return True

    async def open_schedules(self) -> list[Schedule]:
        async with self.session() as s:
            q = await s.execute(select(Schedule).where(Schedule.state.in_(("pending", "notified"))))
            return list(q.scalars())

    async def set_schedule_state(self, schedule_id: int, state: str) -> None:
        async with self.session() as s:
            await s.execute(text("UPDATE schedules SET state = :st WHERE id = :i"), {"st": state, "i": schedule_id})
            await s.commit()

    async def schedule_subscribers(self, schedule_id: int) -> list[int]:
        async with self.session() as s:
            q = await s.execute(select(ScheduleSub.user_id).where(ScheduleSub.schedule_id == schedule_id))
            return list(q.scalars())

    # --- social: cards, clans, weekly tournament -----------------------------------------------

    async def save_card(self, user_id: int, file_id: str, caption: str) -> None:
        async with self.session() as s:
            await s.merge(LastCard(user_id=user_id, file_id=file_id, caption=caption[:1000]))
            await s.commit()

    async def last_card(self, user_id: int) -> LastCard | None:
        async with self.session() as s:
            return await s.get(LastCard, user_id)

    async def clan_of(self, user_id: int) -> Clan | None:
        async with self.session() as s:
            m = await s.get(ClanMember, user_id)
            return await s.get(Clan, m.clan_id) if m else None

    async def create_clan(self, user_id: int, user_name: str, name: str, cost: int) -> str:
        """'ok' | 'member' | 'taken' | 'money'."""
        async with self.session() as s:
            if await s.get(ClanMember, user_id):
                return "member"
            key = name.casefold()
            if (await s.execute(select(Clan.id).where(Clan.name_key == key))).first():
                return "taken"
            await self._ensure(s, user_id, user_name)
            paid = await s.execute(
                text("UPDATE stats SET coins = coins - :c WHERE user_id = :u AND COALESCE(coins, 0) >= :c"),
                {"c": cost, "u": user_id},
            )
            if not paid.rowcount:
                await s.rollback()
                return "money"
            clan = Clan(name=name, name_key=key, owner_id=user_id, created_at=time.time())
            s.add(clan)
            await s.flush()
            s.add(ClanMember(user_id=user_id, clan_id=clan.id, joined_at=time.time()))
            await s.commit()
        return "ok"

    async def join_clan(self, user_id: int, name: str, limit: int) -> tuple[str, Clan | None]:
        """('ok' | 'member' | 'none' | 'full', clan)."""
        async with self.session() as s:
            if await s.get(ClanMember, user_id):
                return "member", None
            clan = (await s.execute(select(Clan).where(Clan.name_key == name.casefold()))).scalar_one_or_none()
            if not clan:
                return "none", None
            count = (
                await s.execute(select(func.count()).select_from(ClanMember).where(ClanMember.clan_id == clan.id))
            ).scalar_one()
            if count >= limit:
                return "full", clan
            s.add(ClanMember(user_id=user_id, clan_id=clan.id, joined_at=time.time()))
            await s.commit()
            return "ok", clan

    async def leave_clan(self, user_id: int) -> bool:
        """Leave; an owner hands the clan to the longest member, the last one out deletes it."""
        async with self.session() as s:
            m = await s.get(ClanMember, user_id)
            if not m:
                return False
            clan = await s.get(Clan, m.clan_id)
            await s.delete(m)
            await s.flush()
            if clan and clan.owner_id == user_id:
                heir = (
                    await s.execute(
                        select(ClanMember).where(ClanMember.clan_id == clan.id).order_by(ClanMember.joined_at).limit(1)
                    )
                ).scalar_one_or_none()
                if heir:
                    clan.owner_id = heir.user_id
                else:
                    await s.delete(clan)
            await s.commit()
        return True

    async def clan_stats(self, clan_id: int, season: str) -> tuple[int, int]:
        """(members, season wins of all members on the global ladder)."""
        async with self.session() as s:
            members = (
                await s.execute(select(func.count()).select_from(ClanMember).where(ClanMember.clan_id == clan_id))
            ).scalar_one()
            wins = (
                await s.execute(
                    select(func.coalesce(func.sum(SeasonStat.wins), 0))
                    .join(ClanMember, ClanMember.user_id == SeasonStat.user_id)
                    .where(ClanMember.clan_id == clan_id, SeasonStat.season == season, SeasonStat.chat_id == 0)
                )
            ).scalar_one()
        return members, int(wins)

    async def clan_top(self, season: str, limit: int = 10) -> list[tuple[str, int, int]]:
        """(name, members, season wins) best first."""
        async with self.session() as s:
            q = await s.execute(
                select(
                    Clan.name,
                    func.count(func.distinct(ClanMember.user_id)),
                    func.coalesce(func.sum(SeasonStat.wins), 0),
                )
                .join(ClanMember, ClanMember.clan_id == Clan.id)
                .outerjoin(
                    SeasonStat,
                    (SeasonStat.user_id == ClanMember.user_id) & (SeasonStat.season == season) & (SeasonStat.chat_id == 0),
                )
                .group_by(Clan.id)
                .order_by(func.coalesce(func.sum(SeasonStat.wins), 0).desc(), Clan.created_at)
                .limit(limit)
            )
            return [(r[0], int(r[1]), int(r[2])) for r in q.all()]

    async def bump_week(self, week: str, user_id: int, name: str, won: bool, pts: int) -> None:
        async with self.session() as s:
            await s.execute(
                text(
                    "INSERT INTO weekly_stats (week, user_id, name, games, wins, points) VALUES (:w, :u, :n, 1, :x, :p)"
                    " ON CONFLICT(week, user_id) DO UPDATE SET name = :n, games = games + 1, wins = wins + :x,"
                    " points = points + :p"
                ),
                {"w": week, "u": user_id, "n": name[:128], "x": 1 if won else 0, "p": pts},
            )
            await s.commit()

    async def week_top(self, week: str, limit: int = 10) -> list[tuple[int, str, int]]:
        """(user_id, name, points) best first; ties go to more wins, then fewer games."""
        async with self.session() as s:
            q = await s.execute(
                select(WeeklyStat.user_id, WeeklyStat.name, WeeklyStat.points)
                .where(WeeklyStat.week == week)
                .order_by(WeeklyStat.points.desc(), WeeklyStat.wins.desc(), WeeklyStat.games)
                .limit(limit)
            )
            return [(r[0], r[1], r[2]) for r in q.all()]

    async def claim_tournament(self, week: str) -> bool:
        """True only the first time a week's prizes are handed out."""
        async with self.session() as s:
            res = await s.execute(
                text("INSERT OR IGNORE INTO tournament_awards (week, at) VALUES (:w, :t)"), {"w": week, "t": time.time()}
            )
            await s.commit()
            return bool(res.rowcount)

    async def grant_badge(self, user_id: int, key: str, emoji: str) -> None:
        """Give a non-purchasable badge (e.g. the tournament trophy) and wear it."""
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
            if not row:
                return
            owned = json.loads(row.badges or "[]")
            if key not in owned:
                row.badges = json.dumps([*owned, key])
            row.badge = emoji
            await s.commit()

    async def award(self, user_id: int, keys: set[str]) -> list[str]:
        """Grant achievements; returns only the ones the user did not have yet."""
        fresh: list[str] = []
        async with self.session() as s:
            for key in sorted(keys):
                res = await s.execute(
                    text("INSERT OR IGNORE INTO achievements (user_id, key, at) VALUES (:u, :k, :t)"),
                    {"u": user_id, "k": key, "t": time.time()},
                )
                if res.rowcount:
                    fresh.append(key)
            await s.commit()
        return fresh

    async def achievement_keys(self, user_id: int) -> set[str]:
        async with self.session() as s:
            return set((await s.execute(select(Achievement.key).where(Achievement.user_id == user_id))).scalars())

    async def achievement_count(self, user_id: int) -> int:
        async with self.session() as s:
            return (
                await s.execute(select(func.count()).select_from(Achievement).where(Achievement.user_id == user_id))
            ).scalar_one()

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
                    "vip_until": None,
                    "badge": "",
                    "xp": 0,
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
                "vip_until": row.vip_until if row.vip_until and row.vip_until > time.time() else None,
                "badge": row.badge or "",
                "xp": row.xp or 0,
            }

    async def credit_wallet(self, user_id: int, name: str, coins: int = 0, gems: int = 0) -> None:
        async with self.session() as s:
            await self._ensure(s, user_id, name)
            await s.execute(
                text(
                    "UPDATE stats SET name = CASE WHEN :n != '' THEN :n ELSE name END, coins = MAX(0, COALESCE(coins, 0) + :c),"
                    " gems = MAX(0, COALESCE(gems, 0) + :g) WHERE user_id = :u"
                ),
                {"n": name[:128], "c": coins, "g": gems, "u": user_id},
            )
            await s.commit()

    # --- Telegram Stars -------------------------------------------------------------------------

    async def record_payment(self, charge_id: str, user_id: int, name: str, product: str, stars: int, coins: int) -> bool:
        """Store a successful payment once; False if this charge was already recorded (update replay)."""
        async with self.session() as s:
            res = await s.execute(
                text(
                    "INSERT OR IGNORE INTO payments (charge_id, user_id, product, stars, coins, created_at)"
                    " VALUES (:ch, :u, :p, :s, :c, :t)"
                ),
                {"ch": charge_id, "u": user_id, "p": product, "s": stars, "c": coins, "t": time.time()},
            )
            if not res.rowcount:
                return False
            await self._ensure(s, user_id, name)
            if coins:
                await s.execute(
                    text("UPDATE stats SET coins = COALESCE(coins, 0) + :c WHERE user_id = :u"), {"c": coins, "u": user_id}
                )
            await s.commit()
        return True

    async def set_vip(self, user_id: int, name: str, until: float) -> None:
        async with self.session() as s:
            await self._ensure(s, user_id, name)
            await s.execute(text("UPDATE stats SET vip_until = :t WHERE user_id = :u"), {"t": until, "u": user_id})
            await s.commit()

    async def vip_until(self, user_id: int) -> float | None:
        async with self.session() as s:
            return (await s.execute(select(UserStat.vip_until).where(UserStat.user_id == user_id))).scalar()

    async def refund(self, charge_id: str) -> Payment | None:
        """Mark a payment refunded and take back what it gave; None if unknown or already refunded."""
        async with self.session() as s:
            pay = await s.get(Payment, charge_id)
            if pay is None or pay.refunded_at:
                return None
            pay.refunded_at = time.time()
            if pay.coins:
                await s.execute(
                    text("UPDATE stats SET coins = MAX(0, COALESCE(coins, 0) - :c) WHERE user_id = :u"),
                    {"c": pay.coins, "u": pay.user_id},
                )
            if pay.product == "vip":
                await s.execute(text("UPDATE stats SET vip_until = NULL WHERE user_id = :u"), {"u": pay.user_id})
            await s.commit()
            return pay

    async def stars_since(self, since: float) -> tuple[int, int]:
        """(payments, stars) received since a moment, refunds excluded."""
        async with self.session() as s:
            row = (
                await s.execute(
                    select(func.count(), func.coalesce(func.sum(Payment.stars), 0)).where(
                        Payment.created_at >= since, Payment.refunded_at.is_(None)
                    )
                )
            ).one()
            return int(row[0]), int(row[1])

    # --- Gem cosmetics --------------------------------------------------------------------------

    async def buy_badge(self, user_id: int, name: str, key: str) -> str:
        """'bought', 'owned' (already had it), 'no_gems' or 'no_item'. Buying or owning also wears it."""
        if key in SPECIAL_BADGES:
            async with self.session() as s:
                row = await s.get(UserStat, user_id)
                if not row or key not in json.loads(row.badges or "[]"):
                    return "no_item"
                row.badge = SPECIAL_BADGES[key][0]
                await s.commit()
            return "owned"
        if key not in BADGES:
            return "no_item"
        emoji, cost = BADGES[key]
        async with self.session() as s:
            await self._ensure(s, user_id, name)
            row = await s.get(UserStat, user_id)
            owned = json.loads(row.badges or "[]")
            if key in owned:
                row.badge = emoji
                await s.commit()
                return "owned"
            res = await s.execute(
                text("UPDATE stats SET gems = gems - :g WHERE user_id = :u AND COALESCE(gems, 0) >= :g"),
                {"g": cost, "u": user_id},
            )
            if not res.rowcount:
                return "no_gems"
            await s.refresh(row)
            row.badges = json.dumps([*owned, key])
            row.badge = emoji
            await s.commit()
        return "bought"

    async def take_off_badge(self, user_id: int) -> None:
        async with self.session() as s:
            await s.execute(text("UPDATE stats SET badge = '' WHERE user_id = :u"), {"u": user_id})
            await s.commit()

    async def shown_badge(self, user_id: int) -> str:
        """The emoji to show before a name: the worn badge, else the VIP mark while VIP is active."""
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
        if not row:
            return ""
        if row.badge:
            return row.badge
        return VIP_BADGE if row.vip_until and row.vip_until > time.time() else ""

    async def owned_badges(self, user_id: int) -> list[str]:
        async with self.session() as s:
            row = await s.get(UserStat, user_id)
        return json.loads(row.badges or "[]") if row else []

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
            spent = await s.execute(
                text("UPDATE stats SET coins = coins - :c WHERE user_id = :u AND COALESCE(coins, 0) >= :c"),
                {"c": cost, "u": user_id},
            )
            if not spent.rowcount:
                return False, "no_money"
            await s.refresh(row)
            try:
                inv = json.loads(row.inventory or "{}")
            except json.JSONDecodeError:
                inv = {}
            if not isinstance(inv, dict):
                inv = {}
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
            spent = await s.execute(
                text("UPDATE stats SET coins = coins - :c WHERE user_id = :u AND COALESCE(coins, 0) >= :c"),
                {"c": ROLE_TICKET_COST, "u": user_id},
            )
            if not spent.rowcount:
                return False, "no_money"
            await s.refresh(row)
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

    async def bump_season(self, season: str, chat_id: int, user_id: int, name: str, won: bool) -> None:
        async with self.session() as s:
            for scope in {0, chat_id}:
                await s.execute(
                    text(
                        "INSERT INTO season_stats (season, chat_id, user_id, name, games, wins) VALUES (:s, :c, :u, :n, 1, :w)"
                        " ON CONFLICT(season, chat_id, user_id) DO UPDATE SET name = :n, games = games + 1, wins = wins + :w"
                    ),
                    {"s": season, "c": scope, "u": user_id, "n": name[:128], "w": 1 if won else 0},
                )
            await s.commit()

    async def season_top(self, season: str, chat_id: int = 0, limit: int = 10) -> list[tuple[str, int, int]]:
        async with self.session() as s:
            q = await s.execute(
                select(SeasonStat)
                .where(SeasonStat.season == season, SeasonStat.chat_id == chat_id)
                .order_by(SeasonStat.wins.desc(), SeasonStat.games.desc())
                .limit(limit)
            )
            return [(r.name or str(r.user_id), r.games, r.wins) for r in q.scalars()]

    async def recent_games(self, chat_id: int, limit: int = 5) -> list[Game]:
        async with self.session() as s:
            q = await s.execute(
                select(GameRow.payload)
                .where(GameRow.chat_id == chat_id, GameRow.status == "finished")
                .order_by(GameRow.updated_at.desc())
                .limit(limit)
            )
            return [from_dict(json.loads(p)) for p in q.scalars()]

    async def top_stats(self, limit: int = 10) -> list[tuple[str, int, int]]:
        async with self.session() as s:
            q = await s.execute(select(UserStat).order_by(UserStat.wins.desc(), UserStat.games.desc()).limit(limit))
            return [(r.name or str(r.user_id), r.games, r.wins) for r in q.scalars()]

    async def chat_settings(self, chat_id: int) -> dict:
        async with self.session() as s:
            row = await s.get(ChatSettings, chat_id)
        try:
            data = json.loads(row.data) if row else {}
        except json.JSONDecodeError:
            data = {}
        return data if isinstance(data, dict) else {}

    async def set_chat_setting(self, chat_id: int, key: str, value: object) -> dict:
        async with self.session() as s:
            row = await s.get(ChatSettings, chat_id)
            data = json.loads(row.data) if row and row.data else {}
            data[key] = value
            if row is None:
                s.add(ChatSettings(chat_id=chat_id, data=json.dumps(data)))
            else:
                row.data = json.dumps(data)
            await s.commit()
        return data

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
