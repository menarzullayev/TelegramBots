from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    CITIZEN = "citizen"
    MAFIA = "mafia"
    DON = "don"
    DETECTIVE = "detective"
    SERGEANT = "sergeant"
    DOCTOR = "doctor"
    MANIAC = "maniac"
    HOOKER = "hooker"
    LAWYER = "lawyer"
    SUICIDE = "suicide"
    HOBO = "hobo"
    LUCKY = "lucky"
    KAMIKAZE = "kamikaze"
    MAYOR = "mayor"
    JOURNALIST = "journalist"
    KILLER = "killer"
    WEREWOLF = "werewolf"
    ARSONIST = "arsonist"
    MAGE = "mage"
    CROOK = "crook"
    SNITCH = "snitch"


class Faction(StrEnum):
    TOWN = "town"
    MAFIA = "mafia"
    NEUTRAL = "neutral"


ROLE_FACTION = {
    Role.CITIZEN: Faction.TOWN,
    Role.DETECTIVE: Faction.TOWN,
    Role.SERGEANT: Faction.TOWN,
    Role.DOCTOR: Faction.TOWN,
    Role.HOOKER: Faction.TOWN,
    Role.HOBO: Faction.TOWN,
    Role.LUCKY: Faction.TOWN,
    Role.KAMIKAZE: Faction.TOWN,
    Role.MAYOR: Faction.TOWN,
    Role.WEREWOLF: Faction.TOWN,
    Role.MAFIA: Faction.MAFIA,
    Role.DON: Faction.MAFIA,
    Role.LAWYER: Faction.MAFIA,
    Role.JOURNALIST: Faction.MAFIA,
    Role.KILLER: Faction.MAFIA,
    Role.MANIAC: Faction.NEUTRAL,
    Role.SUICIDE: Faction.NEUTRAL,
    Role.ARSONIST: Faction.NEUTRAL,
    Role.MAGE: Faction.NEUTRAL,
    Role.CROOK: Faction.NEUTRAL,
    Role.SNITCH: Faction.NEUTRAL,
}

ROLE_UZ = {
    Role.CITIZEN: "Tinch aholi",
    Role.MAFIA: "Qora qo‘l",
    Role.DON: "Don",
    Role.DETECTIVE: "Komissar",
    Role.SERGEANT: "Serjant",
    Role.DOCTOR: "Shifokor",
    Role.MANIAC: "Manyak",
    Role.HOOKER: "Oshiq",
    Role.LAWYER: "Advokat",
    Role.SUICIDE: "O‘z joniga qasd",
    Role.HOBO: "Darvesh",
    Role.LUCKY: "Omadli",
    Role.KAMIKAZE: "Kamikadze",
    Role.MAYOR: "Hokim",
    Role.JOURNALIST: "Jurnalist",
    Role.KILLER: "Qotil",
    Role.WEREWOLF: "Bo‘ri",
    Role.ARSONIST: "O‘t qo‘yuvchi",
    Role.MAGE: "Sehrgar",
    Role.CROOK: "Firibgar",
    Role.SNITCH: "Xufiya",
}

NIGHT_ROLES = {
    Role.MAFIA,
    Role.DON,
    Role.DETECTIVE,
    Role.DOCTOR,
    Role.MANIAC,
    Role.HOOKER,
    Role.LAWYER,
    Role.HOBO,
    Role.JOURNALIST,
    Role.KILLER,
    Role.ARSONIST,
    Role.CROOK,
    Role.SNITCH,
}

HELPER_ROLES = {
    Role.DETECTIVE,
    Role.SERGEANT,
    Role.DOCTOR,
    Role.HOOKER,
    Role.HOBO,
    Role.MAYOR,
}


@dataclass(frozen=True)
class RoleBag:
    mafia: int
    detective: int
    doctor: int
    citizen: int
    don: int = 0
    sergeant: int = 0
    maniac: int = 0
    hooker: int = 0
    lawyer: int = 0
    suicide: int = 0
    hobo: int = 0
    lucky: int = 0
    kamikaze: int = 0
    mayor: int = 0
    journalist: int = 0
    killer: int = 0
    werewolf: int = 0
    arsonist: int = 0
    mage: int = 0
    crook: int = 0
    snitch: int = 0

    @property
    def total(self) -> int:
        return (
            self.mafia
            + self.detective
            + self.doctor
            + self.citizen
            + self.sergeant
            + self.maniac
            + self.hooker
            + self.lawyer
            + self.suicide
            + self.hobo
            + self.lucky
            + self.kamikaze
            + self.mayor
            + self.journalist
            + self.killer
            + self.werewolf
            + self.arsonist
            + self.mage
            + self.crook
            + self.snitch
        )

    def as_list(self) -> list[Role]:
        goons = max(0, self.mafia - self.don)
        return (
            [Role.DON] * self.don
            + [Role.MAFIA] * goons
            + [Role.LAWYER] * self.lawyer
            + [Role.JOURNALIST] * self.journalist
            + [Role.KILLER] * self.killer
            + [Role.DETECTIVE] * self.detective
            + [Role.SERGEANT] * self.sergeant
            + [Role.DOCTOR] * self.doctor
            + [Role.MAYOR] * self.mayor
            + [Role.HOOKER] * self.hooker
            + [Role.HOBO] * self.hobo
            + [Role.LUCKY] * self.lucky
            + [Role.KAMIKAZE] * self.kamikaze
            + [Role.WEREWOLF] * self.werewolf
            + [Role.MANIAC] * self.maniac
            + [Role.SUICIDE] * self.suicide
            + [Role.ARSONIST] * self.arsonist
            + [Role.MAGE] * self.mage
            + [Role.CROOK] * self.crook
            + [Role.SNITCH] * self.snitch
            + [Role.CITIZEN] * self.citizen
        )

    def public_counts(self, lang: str = "uz") -> list[tuple[str, int]]:
        from tezmafia.i18n import role_title

        def name(role: Role) -> str:
            return role_title(lang, role.value) if lang != "uz" else ROLE_UZ[role]

        rows = [
            (name(Role.DON), self.don),
            (name(Role.MAFIA), max(0, self.mafia - self.don)),
            (name(Role.LAWYER), self.lawyer),
            (name(Role.JOURNALIST), self.journalist),
            (name(Role.KILLER), self.killer),
            (name(Role.DETECTIVE), self.detective),
            (name(Role.SERGEANT), self.sergeant),
            (name(Role.DOCTOR), self.doctor),
            (name(Role.MAYOR), self.mayor),
            (name(Role.HOOKER), self.hooker),
            (name(Role.HOBO), self.hobo),
            (name(Role.LUCKY), self.lucky),
            (name(Role.KAMIKAZE), self.kamikaze),
            (name(Role.WEREWOLF), self.werewolf),
            (name(Role.MANIAC), self.maniac),
            (name(Role.SUICIDE), self.suicide),
            (name(Role.ARSONIST), self.arsonist),
            (name(Role.MAGE), self.mage),
            (name(Role.CROOK), self.crook),
            (name(Role.SNITCH), self.snitch),
            (name(Role.CITIZEN), self.citizen),
        ]
        return [(n, c) for n, c in rows if c]


def bag_for(n: int) -> RoleBag:
    """Party-classic counts + city extras peeled from citizens."""
    if n < 5:
        raise ValueError("kamida 5 o‘yinchi")
    if n <= 6:
        mafia, detective, doctor = 1, 1, 0
    elif n <= 8:
        mafia, detective, doctor = 2, 1, 1
    elif n <= 12:
        mafia, detective, doctor = 3, 1, 1
    elif n <= 17:
        mafia, detective, doctor = 4, 1, 1
    else:
        mafia, detective, doctor = 5, 1, 1
    citizen = n - mafia - detective - doctor
    don = 1 if n >= 7 and mafia >= 2 else 0

    def take() -> int:
        nonlocal citizen
        if citizen >= 1:
            citizen -= 1
            return 1
        return 0

    sergeant = take() if n >= 8 else 0
    hooker = take() if n >= 9 else 0
    maniac = take() if n >= 10 else 0
    lawyer = take() if n >= 11 else 0
    mayor = take() if n >= 12 else 0
    suicide = take() if n >= 13 else 0
    lucky = take() if n >= 14 else 0
    kamikaze = take() if n >= 15 else 0
    hobo = take() if n >= 16 else 0
    journalist = take() if n >= 17 else 0
    killer = take() if n >= 18 else 0
    werewolf = take() if n >= 19 else 0
    arsonist = take() if n >= 20 else 0
    mage = take() if n >= 21 else 0
    crook = take() if n >= 22 else 0
    snitch = take() if n >= 23 else 0
    if citizen < 0:  # pragma: no cover — bag_for(5..23) never over-peels
        raise ValueError("fuqaro qolmadi")
    return RoleBag(
        mafia=mafia,
        detective=detective,
        doctor=doctor,
        citizen=citizen,
        don=don,
        sergeant=sergeant,
        maniac=maniac,
        hooker=hooker,
        lawyer=lawyer,
        suicide=suicide,
        hobo=hobo,
        lucky=lucky,
        kamikaze=kamikaze,
        mayor=mayor,
        journalist=journalist,
        killer=killer,
        werewolf=werewolf,
        arsonist=arsonist,
        mage=mage,
        crook=crook,
        snitch=snitch,
    )
