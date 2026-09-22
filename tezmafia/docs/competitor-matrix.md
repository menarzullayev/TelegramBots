# Competitor E2E — TrueMafia vs MafiaAz vs TezMafia

**Status:** closed (DECISION-07 A, 2026-09-21). Bar: live 5p + host UX + 11×21 i18n. Donate klon yo‘q.

Probed 2026-09-21 via live DM + **Qorashahar Lab** (`-1004307184963`).

## Sources

- Live `@TrueMafiaBot` (id 468253535, ~854k users, `truemafia.online`)
- Live `@MafiaAzBot` / Mafia Baku (id 1050428643, ~281k)
- Docs: https://truemafia.ru/howto/ , https://teletype.in/@timagroups/all-roles-in-truemafiabot

## Commands / UX

| Feature              | TrueMafia                                                     | MafiaAz                                                                                           | TezMafia                                                       |
| -------------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Start                | `/game` after delete+restrict+pin                             | `/game` after admin                                                                               | `/mafia` `/game` `/newgame`                                    |
| Join                 | DM deep-link `?start=G_…`                                     | DM `?start=-100…_0`                                                                               | Join + DM `?start=g_`                                          |
| Leave                | `/leave`                                                      | `/leave`                                                                                          | `/leave` + tugma                                               |
| Stop                 | `/stop`                                                       | `/stop` → «O'yin to'xtatildi.»                                                                    | `/stop` `/cancel`                                              |
| Extend               | `/extend` `/prolong`                                          | `/extend` (bir marta)                                                                             | `/extend` `/prolong` (3×)                                      |
| Next phase           | `/next`                                                       | bor                                                                                               | `/next` (host)                                                 |
| Roles catalog        | 13 inline                                                     | `/roles` 20+                                                                                      | `/roles` + `hr:` kartalar                                      |
| Profile              | money/gems/store                                              | `/profile` (avval til)                                                                            | `/profile` $ / olmos / sumka                                   |
| Shop                 | GO: Защита / Документы / Активная роль; `/shop`=`/help` menyu | GO: Himoya, Qotildan himoya, Ovoz, Miltiq, Maska, Soxta hujjat, Keyingi rol; `/shop`=`/start` til | `/shop` + `/buy maska` + `/buy role komissar`; 6 item + ticket |
| Top                  | faqat supergroup                                              | `/top`                                                                                            | `/top`                                                         |
| Language             | ko‘p + UZ                                                     | 11 til, UZ ishlaydi                                                                               | `/settings` 11 kod; gameplay `t(lang)` 21 rol + fazalar        |
| Night mute + delete  | ha                                                            | ha                                                                                                | mute + night delete                                            |
| Lynch confirm        | ikkinchi ovoz                                                 | ovoz 45s, kelishmovchilik                                                                         | `ly:` Ha/Yo‘q                                                  |
| Custom emoji / style | oddiy                                                         | oddiy                                                                                             | VectorGuard + style                                            |

## Roles (playable in TezMafia)

21 rol: tinch, qora qo‘l, don, komissar (1-tun **faqat tekshir**, keyin tekshir **yoki otish**), serjant, shifokor, manyak, oshiq, advokat, o‘z joniga qasd, darvesh, omadli, kamikadze, hokim, jurnalist, qotil, bo‘ri, o‘t qo‘yuvchi, sehrgar, firibgar, xufiya.

Bag: 5–16 TrueMafia set; 17–23 MafiaAz extra (jurnalist…xufiya). Force-assign har qanday o‘yinda.

## Live Lab

- Basic group `CHANNEL_INVALID` — faqat supergroup.
- TrueMafia: admin OK → `/game` «Ведётся набор» + join link; min **4**; kam o‘yinchida yopiladi.
- MafiaAz: UZ welcome; `/extend` bir marta; `/stop@MafiaAzBot` to‘xtatadi.
- Testers Labga qo‘shildi: `@NarzullayevPro` `@NarzullayevProMax` `@oqNarzullayev`.
- TrueMafia `/top` Labda: faqat Black-versiya (`@TrueMafiaBlackBot`).
- **Live TrueMafia 4p (2026-09-21 STY, 3:55):** oqNarzullayev(Don) + saidakbar(Doctor) + NarzullayevPro(citizen) + NarzullayevS(citizen). Tun mute/delete; miss; kun bag; ovoz URL DM. AFK 2 tun → o‘lim + last words. GO: «Победили: Мирные жители». Shop pul/tosh.
- **Live MafiaAz 5p (2026-09-21, 3 daqiqa):** saidakbar(Don) + NarzullayevS(Kezuvchi/Hooker) + Segment Off Σ(Komissar) + NarzullayevPro(Doktor) + oqNarzullayev(tinch). `/start`/`/next` → «O'yin boshlandi!» + rol DM. Tun-1 miss; kun bag 5 rol; ovoz 45s DM; kelishmovchilik. Tun-2 AFK: komissar/doktor/don/kezuvchi last words «Men o'yin paytida boshqa uxlamayma-a-an!». GO: tinch (oqNarzullayev). Shop dollar/olmos.
- Join skript: handlechecker `.venv` (pyrogram); `--payload -100…` argparse yopishtiriladi.
- TezMafia: tun roli 2 tun harakatsiz → AFK o‘lim + last words (citizen/mayor/lucky/… tun roli emas — omon).
- **Live TezMafia 5p (2026-09-21, `g_lSbVo9xZYk4`):** 5/5 DM OK → `/startgame`. Bag: 1 qora qo‘l + 1 komissar + 3 tinch. saidakbar(mafia) + NarzullayevS(tinch). Tun-1 miss; kun; `/next` sud. Tun-2 AFK: mafia + komissar o‘ldi. GO: «Shahar nafas oldi».
- **Live TezMafia shop (2026-09-21, DM `@qorashahar_mafia_bot`):** `/shop` katalog (tun/sud himoya, maska, soxta hujjat, miltiq) + buy tugmalari. `/profile` dollar/olmos/sumka. `tezmafia.service` PID 1440208.
- **Live TezMafia 5p (2026-09-21, `g_5ZfdBtHNMlQ`):** saidakbar=Komissar — DM «Birinchi tunda faqat tekshirasiz», tun-1 tugmalar faqat `nd:` (otish yo‘q). Tun-2 AFK: komissar + qora qo‘l o‘ldi. **GO last words** «Men o‘yin paytida boshqa uxlamayma-a-an!» + «Shahar nafas oldi». NarzullayevS guruhda `/vote` yozildi (CHAT_WRITE_FORBIDDEN yo‘q).
- **Competitor DM (2026-09-21 ~22:28):** TrueMafia `/help`/`/shop` → host menyu (Add chat, Enter, Language, Profile, Roles). Shop itemlar GO da: Защита / Документы / Активная роль + Купить 💵/💎. MafiaAz `/start`/`/shop`/`/help` → til tanlash; shop itemlar GO da: Himoya, Qotildan himoya, Ovoz himoya, Miltiq, Maska, Soxta hujjat, Keyingi rol + Xarid 💵/💎. Real-money donate klon qilinmaydi.
- **Live TezMafia shop (2026-09-21 22:29–22:31):** `/buy maska` → «Sotib olindi» + katalog $65, Maska×1, **Qotildan himoya**. `/buy role komissar` → profil «Keyingi rol: Komissar», $30. `/help` rich + keyin «Tez yo‘llar» menyu (Profil/Do‘kon/Rollar/Til). Real-money donate klon qilinmaydi. pytest **53 passed**, cov **97%**.
- **DECISION-04 live 5p (2026-09-21, `g_sODQ5fp3j-U`, PID 1672943):** 5/5 DM OK → `/startgame`. Host `@menarzullayev` ticket **Komissar** (DM «Birinchi tunda faqat tekshirasiz»); Tun-1 tugmalar faqat `nd:` (otish yo‘q). `@NarzullayevS` ikkinchi komissar ticket → **tinch aholi** + `/profile` **$35** (first-wins refund). Host mask loadout: inventar bo‘sh, `shop_mask=True`. Tun-1 miss → Kun 1. Donate klon yo‘q.
- **DECISION-04 competitor katalog (2026-09-21 ~23:14–23:21):** TrueMafia `/help` host menyu (Add chat URL, Enter=`get_chats`, Language, Profile, Roles); `/profile` money/gems + Store/Purchase💵/Purchase💎 (`donate_home` bosilmadi). MafiaAz `/start`/`/shop`/`/profile` → 11 til; `/roles` to‘liq EN katalog (Detective N1 no-shoot yozuvi bor). Inline `request_callback_answer` → **TimeoutError** (menu_profile, page2:Language:uz); buyruq fallback ishlatildi.
- **DECISION-05 host UX (2026-09-21, PID 1718842):** `/start` (1777924) TrueMafia-uslub host menyu. `/settings` (1777926) 11 til. `/chats` empty (1777928) → Lab lobby `g_0ZxOw6urRb4` → `/chats` (1777930) + `/enter` (1777932) «ochiq stollaringiz: 1» + `Stol lobby · 1p`. Gameplay uz. Donate klon yo‘q.
- **DECISION-06 gameplay i18n (2026-09-21, PID 1803316):** 11×223 katalog. Live DM `en`: `/roles` (1777935) Detective/Citizen/Black Hand 21 tugma; `/settings` (1777938) «Game text in this language.»; `/start` (1777939) EN host menyu. Donate klon yo‘q.
