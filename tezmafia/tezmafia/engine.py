from __future__ import annotations

import html
import secrets
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from tezmafia.roles import HELPER_ROLES, NIGHT_ROLES, ROLE_FACTION, Faction, Role, RoleBag, bag_for


class Phase(StrEnum):
    LOBBY = "lobby"
    ROLE_ASSIGNMENT = "role_assignment"
    NIGHT = "night"
    DAY = "day"
    VOTING = "voting"
    LYNCH = "lynch"
    FINISHED = "finished"


class Winner(StrEnum):
    TOWN = "town"
    MAFIA = "mafia"
    MANIAC = "maniac"
    SUICIDE = "suicide"
    ARSONIST = "arsonist"
    SNITCH = "snitch"
    MAGE = "mage"
    CROOK = "crook"


@dataclass
class Player:
    user_id: int
    first_name: str
    username: str | None
    seat: int
    role: str | None = None
    faction: str | None = None
    alive: bool = True
    dm_ok: bool = False
    night_action: int | None = None
    vote: int | None = None
    blocked: bool = False
    lucky_used: bool = False
    doctor_self_used: bool = False
    lynch_yes: bool | None = None
    detective_mode: str | None = None
    idle_nights: int = 0
    shop_shield: bool = False
    shop_vote_shield: bool = False
    shop_mask: bool = False
    shop_fake_id: bool = False
    shop_gun: bool = False
    shop_killer_shield: bool = False

    def label(self) -> str:
        if self.username:
            return f"{self.first_name} (@{self.username})"
        return self.first_name

    def html_label(self) -> str:
        name = html.escape(self.first_name)
        if self.username:
            return f"{name} (@{html.escape(self.username)})"
        return name

    def vote_weight(self) -> int:
        return 2 if self.role == Role.MAYOR else 1


@dataclass
class Game:
    id: str
    chat_id: int
    host_id: int
    phase: str = Phase.LOBBY
    round: int = 0
    players: list[Player] = field(default_factory=list)
    winner: str | None = None
    last_death_seat: int | None = None
    last_death_cause: str | None = None
    last_death_role: str | None = None
    night_saved: bool = False
    night_miss: bool = False
    detective_result: dict[str, Any] | None = None
    version: int = 0
    created_at: float = field(default_factory=time.time)
    deadline: float | None = None
    lobby_message_id: int | None = None
    vote_message_id: int | None = None
    min_players: int = 5
    max_players: int = 23
    mafia_resolve: str = "majority"
    reveal_on_death: bool = True
    first_phase: str = "night_kill"
    lynch_seat: int | None = None
    lobby_extends: int = 0
    night_deaths: list[int] = field(default_factory=list)
    hobo_seen: dict[str, Any] | None = None
    lawyer_cover: int | None = None
    journalist_result: dict[str, Any] | None = None
    crook_mask: int | None = None
    arson_marks: list[int] = field(default_factory=list)
    arson_kills: int = 0
    snitch_hit: bool = False
    afk_deaths: list[int] = field(default_factory=list)
    masked_deaths: list[int] = field(default_factory=list)
    night_no: int = 0

    def by_user(self, user_id: int) -> Player | None:
        return next((p for p in self.players if p.user_id == user_id), None)

    def by_seat(self, seat: int) -> Player | None:
        return next((p for p in self.players if p.seat == seat), None)

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def alive_mafia(self) -> list[Player]:
        return [p for p in self.alive_players() if p.faction == Faction.MAFIA]

    def alive_town(self) -> list[Player]:
        return [p for p in self.alive_players() if p.faction == Faction.TOWN]

    def alive_role(self, role: Role | str) -> list[Player]:
        key = role.value if isinstance(role, Role) else role
        return [p for p in self.alive_players() if p.role == key]


def new_game(chat_id: int, host_id: int, **cfg: Any) -> Game:
    return Game(
        id=secrets.token_urlsafe(8),
        chat_id=chat_id,
        host_id=host_id,
        **cfg,
    )


def join(game: Game, user_id: int, first_name: str, username: str | None) -> tuple[bool, str]:
    if game.phase != Phase.LOBBY:
        return False, "lobby_closed"
    existing = game.by_user(user_id)
    if existing:
        return True, "already"
    if len(game.players) >= game.max_players:
        return False, "full"
    game.players.append(
        Player(
            user_id=user_id,
            first_name=first_name,
            username=username,
            seat=len(game.players) + 1,
        )
    )
    game.version += 1
    return True, "joined"


def leave(game: Game, user_id: int) -> bool:
    if game.phase != Phase.LOBBY:
        return False
    before = len(game.players)
    game.players = [p for p in game.players if p.user_id != user_id]
    for i, p in enumerate(game.players, start=1):
        p.seat = i
    if len(game.players) != before:
        game.version += 1
        return True
    return False


def mark_dm_ok(game: Game, user_id: int) -> bool:
    p = game.by_user(user_id)
    if not p:
        return False
    if not p.dm_ok:
        p.dm_ok = True
        game.version += 1
    return True


def can_start(game: Game) -> tuple[bool, str]:
    if game.phase != Phase.LOBBY:
        return False, "not_lobby"
    if len(game.players) < game.min_players:
        return False, "too_few"
    if not all(p.dm_ok for p in game.players):
        return False, "dm_pending"
    return True, "ok"


def extend_lobby(game: Game, seconds: int, max_extends: int = 3) -> tuple[bool, str]:
    if game.phase != Phase.LOBBY:
        return False, "not_lobby"
    if game.lobby_extends >= max_extends:
        return False, "no_extend"
    game.lobby_extends += 1
    now = time.time()
    base = game.deadline if game.deadline and game.deadline > now else now
    game.deadline = base + seconds
    game.version += 1
    return True, "ok"


def start(game: Game, rng: Any = None) -> RoleBag:
    ok, reason = can_start(game)
    if not ok:
        raise RuntimeError(reason)
    import random

    bag = bag_for(len(game.players))
    roles = bag.as_list()
    (rng or random).shuffle(roles)
    for player, role in zip(game.players, roles, strict=True):
        player.role = role.value
        player.faction = ROLE_FACTION[role].value
        player.alive = True
        player.night_action = None
        player.vote = None
        player.blocked = False
        player.lucky_used = False
        player.doctor_self_used = False
        player.lynch_yes = None
        player.detective_mode = None
        player.idle_nights = 0
        player.shop_shield = False
        player.shop_vote_shield = False
        player.shop_mask = False
        player.shop_fake_id = False
        player.shop_gun = False
        player.shop_killer_shield = False
    game.phase = Phase.ROLE_ASSIGNMENT
    game.round = 0
    game.night_no = 0
    game.masked_deaths = []
    game.winner = None
    game.version += 1
    return bag


def begin_night(game: Game, now: float, seconds: int) -> None:
    game.phase = Phase.NIGHT
    game.round += 1
    game.night_no += 1
    game.last_death_seat = None
    game.last_death_cause = None
    game.last_death_role = None
    game.night_saved = False
    game.night_miss = False
    game.detective_result = None
    game.lynch_seat = None
    game.night_deaths = []
    game.hobo_seen = None
    game.lawyer_cover = None
    game.journalist_result = None
    game.crook_mask = None
    game.afk_deaths = []
    for p in game.players:
        p.night_action = None
        p.vote = None
        p.detective_mode = None
        p.blocked = False
        p.lynch_yes = None
    game.deadline = now + seconds
    game.version += 1


def set_night_action(game: Game, user_id: int, target_seat: int, kind: str = "") -> tuple[bool, str]:
    if game.phase != Phase.NIGHT:
        return False, "not_night"
    actor = game.by_user(user_id)
    target = game.by_seat(target_seat)
    if not actor or not actor.alive:
        return False, "dead"
    if not target or not target.alive:
        return False, "bad_target"
    role = Role(actor.role) if actor.role else None
    if role not in NIGHT_ROLES:
        if actor.shop_gun:
            if target.user_id == actor.user_id:
                return False, "no_self"
            actor.night_action = target_seat
            actor.detective_mode = "gun"
            game.version += 1
            return True, "ok"
        return False, "no_action"
    no_self = {
        Role.MAFIA,
        Role.DON,
        Role.DETECTIVE,
        Role.MANIAC,
        Role.HOOKER,
        Role.HOBO,
        Role.JOURNALIST,
        Role.KILLER,
        Role.CROOK,
        Role.SNITCH,
    }
    if role in no_self and target.user_id == actor.user_id:
        return False, "no_self"
    if role == Role.DOCTOR and target.user_id == actor.user_id and actor.doctor_self_used:
        return False, "self_used"
    if role in (Role.MAFIA, Role.DON, Role.KILLER) and target.faction == Faction.MAFIA and target.user_id != actor.user_id:
        return False, "no_teamkill"
    if role == Role.DETECTIVE and kind == "shoot" and game.night_no <= 1:
        return False, "no_first_shoot"
    actor.night_action = target_seat
    if role == Role.DETECTIVE:
        actor.detective_mode = "shoot" if kind == "shoot" else "check"
    game.version += 1
    return True, "ok"


def _mafia_target(game: Game) -> int | None:
    voters = [p for p in game.alive_mafia() if p.role in (Role.MAFIA, Role.DON) and p.night_action]
    votes = [p.night_action for p in voters if p.night_action]
    if not votes:
        return None
    counts = Counter(votes)
    top_n, top_c = counts.most_common(1)[0]
    don = next((p for p in voters if p.role == Role.DON), None)
    if game.mafia_resolve == "unanimous":
        needed = [p for p in game.alive_mafia() if p.role in (Role.MAFIA, Role.DON)]
        if len(votes) == len(needed) and len(counts) == 1:
            return top_n
        return None
    if game.mafia_resolve == "first":
        return votes[0]
    if list(counts.values()).count(top_c) > 1:
        if don and don.night_action:
            return don.night_action
        return None
    if game.mafia_resolve == "majority":
        need = (len([p for p in game.alive_mafia() if p.role in (Role.MAFIA, Role.DON)]) + 1) // 2
        if top_c < need:
            return None
    return top_n


def _promote_sergeant(game: Game) -> None:
    if game.alive_role(Role.DETECTIVE):
        return
    sgt = next(iter(game.alive_role(Role.SERGEANT)), None)
    if sgt:
        sgt.role = Role.DETECTIVE.value


def _try_kill(
    game: Game,
    player: Player | None,
    cause: str,
    killer: Player | None = None,
) -> bool:
    if not player or not player.alive:
        return False
    if player.role == Role.MAGE and cause == "night":
        if killer and killer.alive and killer.user_id != player.user_id:
            killer.alive = False
            game.night_deaths.append(killer.seat)
            game.last_death_seat = killer.seat
            game.last_death_cause = "mage"
            game.last_death_role = killer.role if game.reveal_on_death else None
        return False
    if (
        player.role == Role.WEREWOLF
        and cause == "night"
        and killer
        and killer.faction == Faction.MAFIA
    ):
        player.faction = Faction.MAFIA.value
        return False
    if player.role == Role.LUCKY and not player.lucky_used:
        player.lucky_used = True
        return False
    if player.shop_shield and cause == "night":
        player.shop_shield = False
        return False
    if (
        player.shop_killer_shield
        and cause == "night"
        and killer
        and killer.role == Role.KILLER
    ):
        player.shop_killer_shield = False
        return False
    player.alive = False
    game.last_death_seat = player.seat
    game.last_death_cause = cause
    hide = player.shop_mask or not game.reveal_on_death
    game.last_death_role = None if hide else player.role
    if player.shop_mask:
        player.shop_mask = False
        game.masked_deaths.append(player.seat)
    if cause in ("night", "afk"):
        game.night_deaths.append(player.seat)
    if player.role == Role.KAMIKAZE and cause == "night":
        boom = killer if killer and killer.alive else next(iter(game.alive_mafia()), None)
        if boom:
            boom.alive = False
            game.night_deaths.append(boom.seat)
    return True


def resolve_night(game: Game) -> dict[str, Any]:
    if game.phase != Phase.NIGHT:
        raise RuntimeError("not_night")
    acted = {p.user_id for p in game.alive_players() if p.night_action}
    hookers = game.alive_role(Role.HOOKER)
    blocked_ids: set[int] = set()
    for h in hookers:
        if h.night_action:
            tgt = game.by_seat(h.night_action)
            if tgt and tgt.alive:
                tgt.night_action = None
                tgt.blocked = True
                blocked_ids.add(tgt.user_id)

    lawyers = game.alive_role(Role.LAWYER)
    covered = {p.night_action for p in lawyers if p.night_action}
    game.lawyer_cover = next(iter(covered), None)

    hobos = game.alive_role(Role.HOBO)
    hobo_visits = {h.user_id: h.night_action for h in hobos if h.night_action}

    target = _mafia_target(game)
    maniacs = game.alive_role(Role.MANIAC)
    maniac_target = maniacs[0].night_action if maniacs and maniacs[0].night_action else None

    doctors = game.alive_role(Role.DOCTOR)
    protect = doctors[0].night_action if doctors else None
    if doctors and protect == doctors[0].seat:
        doctors[0].doctor_self_used = True

    detectives = game.alive_role(Role.DETECTIVE)
    detective_shoot = False
    if detectives and detectives[0].night_action:
        if detectives[0].detective_mode == "shoot":
            detective_shoot = True
        else:
            checked = game.by_seat(detectives[0].night_action)
            if checked:
                looks_mafia = checked.faction == Faction.MAFIA
                if checked.role == Role.DON or checked.seat in covered or checked.shop_fake_id:
                    looks_mafia = False
                game.detective_result = {
                    "seat": checked.seat,
                    "is_mafia": looks_mafia,
                    "detective_id": detectives[0].user_id,
                }

    journalists = game.alive_role(Role.JOURNALIST)
    if journalists and journalists[0].night_action:
        seat = journalists[0].night_action
        visitors = [
            p.seat
            for p in game.alive_players()
            if p.night_action == seat and p.user_id != journalists[0].user_id
        ]
        watched = game.by_seat(seat)
        helper = bool(watched and watched.role and Role(watched.role) in HELPER_ROLES)
        game.journalist_result = {
            "seat": seat,
            "visitors": visitors,
            "helper": helper,
            "journalist_id": journalists[0].user_id,
        }

    snitches = game.alive_role(Role.SNITCH)
    if (
        snitches
        and detectives
        and snitches[0].night_action
        and detectives[0].night_action
        and snitches[0].night_action == detectives[0].night_action
        and detectives[0].detective_mode != "shoot"
    ):
        game.snitch_hit = True

    crooks = game.alive_role(Role.CROOK)
    if crooks and crooks[0].night_action:
        game.crook_mask = crooks[0].night_action

    visitors = [seat for seat in (target, maniac_target, protect) if seat]
    if hobos and hobo_visits:
        seen = [s for s in visitors if s]
        game.hobo_seen = {"seats": seen, "hobo_id": hobos[0].user_id}

    def _hobo_home(seat: int | None) -> bool:
        if seat is None:
            return True
        victim = game.by_seat(seat)
        if not victim or victim.role != Role.HOBO:
            return True
        return victim.night_action in (None, victim.seat)

    game.night_miss = target is None
    game.night_saved = bool(target and protect == target)
    killed: Player | None = None

    def apply(seat: int | None, killer: Player | None = None, ignore_protect: bool = False) -> None:
        nonlocal killed
        if not seat:
            return
        if protect == seat and not ignore_protect:
            game.night_saved = True
            return
        if not _hobo_home(seat):
            game.night_miss = True
            return
        victim = game.by_seat(seat)
        if _try_kill(game, victim, "night", killer=killer):
            killed = victim
            for h in hobos:
                if h.alive and h.night_action == seat:
                    _try_kill(game, h, "night", killer=killer)

    mafia_killer = next((p for p in game.alive_mafia() if p.role in (Role.MAFIA, Role.DON)), None)
    apply(target, killer=mafia_killer)
    if maniac_target and maniac_target != target:
        apply(maniac_target, killer=maniacs[0] if maniacs else None)

    killers = game.alive_role(Role.KILLER)
    if killers and killers[0].night_action:
        kt = game.by_seat(killers[0].night_action)
        if kt and kt.role == Role.DETECTIVE:
            _try_kill(game, killers[0], "night", killer=kt)
        else:
            apply(killers[0].night_action, killer=killers[0], ignore_protect=True)

    if detective_shoot and detectives[0].night_action:
        apply(detectives[0].night_action, killer=detectives[0])

    for shooter in [p for p in game.alive_players() if p.shop_gun and p.detective_mode == "gun" and p.night_action]:
        apply(shooter.night_action, killer=shooter)
        shooter.shop_gun = False

    arsonists = game.alive_role(Role.ARSONIST)
    if arsonists and arsonists[0].night_action:
        mark = arsonists[0].night_action
        if mark == arsonists[0].seat:
            for seat in list(game.arson_marks):
                if seat == arsonists[0].seat:
                    continue
                before = game.by_seat(seat)
                apply(seat, killer=arsonists[0], ignore_protect=True)
                after = game.by_seat(seat)
                if before and after and not after.alive:
                    game.arson_kills += 1
            game.arson_marks = []
        elif mark not in game.arson_marks:
            game.arson_marks.append(mark)

    afk: list[int] = []
    for p in list(game.alive_players()):
        night_duty = (p.role and Role(p.role) in NIGHT_ROLES) or p.shop_gun
        if not night_duty:
            continue
        if p.user_id in acted:
            p.idle_nights = 0
            continue
        p.idle_nights += 1
        if p.idle_nights >= 2 and _try_kill(game, p, "afk"):
            afk.append(p.seat)
    game.afk_deaths = afk

    _promote_sergeant(game)
    winner = win_check(game)
    game.phase = Phase.FINISHED if winner else Phase.DAY
    game.deadline = None
    game.version += 1
    return {
        "killed": killed.seat if killed else None,
        "saved": game.night_saved,
        "miss": game.night_miss,
        "winner": winner,
        "detective_result": game.detective_result,
        "journalist_result": game.journalist_result,
        "blocked": list(blocked_ids),
        "deaths": list(game.night_deaths),
        "afk": afk,
    }


def begin_voting(game: Game, now: float, seconds: int) -> None:
    if game.phase not in (Phase.DAY, Phase.VOTING):
        raise RuntimeError("not_day")
    for p in game.players:
        p.vote = None
    game.vote_message_id = None
    game.phase = Phase.VOTING
    game.deadline = now + seconds
    game.version += 1


def set_vote(game: Game, user_id: int, target_seat: int | None) -> tuple[bool, str]:
    if game.phase != Phase.VOTING:
        return False, "not_voting"
    actor = game.by_user(user_id)
    if not actor or not actor.alive:
        return False, "dead"
    if actor.blocked:
        return False, "blocked"
    if target_seat is None:
        actor.vote = None
        game.version += 1
        return True, "cleared"
    target = game.by_seat(target_seat)
    if not target or not target.alive:
        return False, "bad_target"
    if target.user_id == actor.user_id:
        return False, "no_self"
    actor.vote = target_seat
    game.version += 1
    return True, "ok"


def peek_votes(game: Game) -> tuple[int | None, bool, dict[int, int]]:
    if game.crook_mask:
        crook = next(iter(game.alive_role(Role.CROOK)), None)
        victim = game.by_seat(game.crook_mask)
        if crook and crook.alive and crook.vote and victim and victim.alive:
            victim.vote = crook.vote
    votes: list[int] = []
    for p in game.alive_players():
        if p.vote:
            votes.extend([p.vote] * p.vote_weight())
    if not votes:
        return None, False, {}
    counts = Counter(votes)
    top_seat, top_c = counts.most_common(1)[0]
    if list(counts.values()).count(top_c) > 1:
        return None, True, dict(counts)
    return top_seat, False, dict(counts)


def _after_elim(game: Game, eliminated: Player | None) -> str | None:
    if eliminated and eliminated.role == Role.SUICIDE and game.last_death_cause == "vote":
        game.winner = Winner.SUICIDE
        game.phase = Phase.FINISHED
        return Winner.SUICIDE
    _promote_sergeant(game)
    if eliminated and eliminated.role == Role.KAMIKAZE and game.last_death_cause == "vote":
        extra = next((p for p in game.alive_players() if p.vote == eliminated.seat), None)
        if extra:
            extra.alive = False
    return win_check(game)


def resolve_votes(game: Game) -> dict[str, Any]:
    if game.phase != Phase.VOTING:
        raise RuntimeError("not_voting")
    top_seat, tie, tally = peek_votes(game)
    eliminated: Player | None = None
    if top_seat and not tie:
        eliminated = game.by_seat(top_seat)
        if eliminated and game.lawyer_cover == eliminated.seat:
            eliminated = None
        elif eliminated and eliminated.shop_vote_shield:
            eliminated.shop_vote_shield = False
            eliminated = None
        elif eliminated:
            _try_kill(game, eliminated, "vote")
    winner = _after_elim(game, eliminated if eliminated and not eliminated.alive else None)
    if winner:
        game.phase = Phase.FINISHED
    else:
        game.phase = Phase.DAY
    game.deadline = None
    game.version += 1
    return {
        "eliminated": eliminated.seat if eliminated and not eliminated.alive else None,
        "tie": tie,
        "winner": winner,
        "tally": tally,
    }


def begin_lynch(game: Game, seat: int, now: float, seconds: int) -> None:
    game.phase = Phase.LYNCH
    game.lynch_seat = seat
    for p in game.players:
        p.lynch_yes = None
    game.deadline = now + seconds
    game.version += 1


def set_lynch_vote(game: Game, user_id: int, yes: bool) -> tuple[bool, str]:
    if game.phase != Phase.LYNCH:
        return False, "not_lynch"
    actor = game.by_user(user_id)
    target = game.by_seat(game.lynch_seat or -1)
    if not actor or not actor.alive:
        return False, "dead"
    if not target or actor.user_id == target.user_id:
        return False, "no_self"
    actor.lynch_yes = yes
    game.version += 1
    return True, "ok"


def resolve_lynch(game: Game) -> dict[str, Any]:
    if game.phase != Phase.LYNCH:
        raise RuntimeError("not_lynch")
    yes = sum(1 for p in game.alive_players() if p.lynch_yes is True)
    no = sum(1 for p in game.alive_players() if p.lynch_yes is False)
    eliminated: Player | None = None
    confirmed = yes > no
    if confirmed and game.lynch_seat:
        eliminated = game.by_seat(game.lynch_seat)
        if eliminated and game.lawyer_cover == eliminated.seat:
            eliminated = None
        elif eliminated and eliminated.shop_vote_shield:
            eliminated.shop_vote_shield = False
            eliminated = None
        elif eliminated:
            _try_kill(game, eliminated, "vote")
    winner = _after_elim(game, eliminated if eliminated and not eliminated.alive else None)
    if winner:
        game.phase = Phase.FINISHED
    else:
        game.phase = Phase.DAY
    game.deadline = None
    game.version += 1
    return {
        "eliminated": eliminated.seat if eliminated and not eliminated.alive else None,
        "confirmed": confirmed,
        "yes": yes,
        "no": no,
        "winner": winner,
    }


def after_day_announce_night(game: Game, now: float, seconds: int) -> None:
    if game.phase == Phase.FINISHED:
        return
    begin_night(game, now, seconds)


def win_check(game: Game) -> str | None:
    if game.snitch_hit:
        game.winner = Winner.SNITCH
        game.phase = Phase.FINISHED
        return Winner.SNITCH
    if game.arson_kills >= 3:
        game.winner = Winner.ARSONIST
        game.phase = Phase.FINISHED
        return Winner.ARSONIST
    alive = game.alive_players()
    if len(alive) == 1 and alive[0].role == Role.MAGE:
        game.winner = Winner.MAGE
        game.phase = Phase.FINISHED
        return Winner.MAGE
    if len(alive) == 1 and alive[0].role == Role.CROOK:
        game.winner = Winner.CROOK
        game.phase = Phase.FINISHED
        return Winner.CROOK
    m = len(game.alive_mafia())
    t = len(game.alive_town())
    maniacs = len(game.alive_role(Role.MANIAC))
    suicides = len(game.alive_role(Role.SUICIDE))
    extra = (
        len(game.alive_role(Role.ARSONIST))
        + len(game.alive_role(Role.MAGE))
        + len(game.alive_role(Role.CROOK))
        + len(game.alive_role(Role.SNITCH))
    )
    if m == 0 and maniacs == 0 and extra == 0 and (t + suicides) > 0:
        game.winner = Winner.TOWN
        game.phase = Phase.FINISHED
        return Winner.TOWN
    if maniacs > 0 and m == 0 and t == 0 and extra == 0:
        game.winner = Winner.MANIAC
        game.phase = Phase.FINISHED
        return Winner.MANIAC
    if m > 0 and m >= (t + maniacs + suicides + extra):
        game.winner = Winner.MAFIA
        game.phase = Phase.FINISHED
        return Winner.MAFIA
    return None


def cancel(game: Game) -> None:
    game.phase = Phase.FINISHED
    game.deadline = None
    game.version += 1


def dm_pending(game: Game) -> list[Player]:
    return [p for p in game.players if not p.dm_ok]


def to_dict(game: Game) -> dict[str, Any]:
    return asdict(game)


def from_dict(data: dict[str, Any]) -> Game:
    players = []
    for p in data.get("players", []):
        row = dict(p)
        row.setdefault("detective_mode", None)
        row.setdefault("idle_nights", 0)
        row.setdefault("shop_shield", False)
        row.setdefault("shop_vote_shield", False)
        row.setdefault("shop_mask", False)
        row.setdefault("shop_fake_id", False)
        row.setdefault("shop_gun", False)
        row.setdefault("shop_killer_shield", False)
        players.append(Player(**row))
    raw = dict(data)
    raw["players"] = players
    raw.setdefault("night_deaths", [])
    raw.setdefault("lynch_seat", None)
    raw.setdefault("lobby_extends", 0)
    raw.setdefault("hobo_seen", None)
    raw.setdefault("lawyer_cover", None)
    raw.setdefault("journalist_result", None)
    raw.setdefault("crook_mask", None)
    raw.setdefault("arson_marks", [])
    raw.setdefault("arson_kills", 0)
    raw.setdefault("snitch_hit", False)
    raw.setdefault("afk_deaths", [])
    raw.setdefault("masked_deaths", [])
    raw.setdefault("night_no", 0)
    return Game(**raw)
