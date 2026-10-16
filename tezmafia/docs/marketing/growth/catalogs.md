# TezMafia: bot and channel catalogs, plus submission kit

Owner submits everything (accounts, forms). Texts extend `docs/marketing/catalog-and-ads.md`.
VERIFIED = I opened the page or an official doc in this session. Everything else is UNVERIFIED:
open the site and read its current rules before submitting.

## 1. Where to list

| # | Place | URL | Submit | Cost | Status |
|---|---|---|---|---|---|
| 1 | Telegram search + Main Mini App (BotFather) | BotFather, `/mybots`, Bot Settings, Configure Mini App, set Main Mini App | Main Mini App `https://mafia.bugvector.uz`, media previews (per language), descriptions | Free | VERIFIED in https://core.telegram.org/bots/webapps: a Main Mini App adds a "Launch app" button, shows the bot in the Apps tab of search, and bots with a Main Mini App plus Stars payments "may be featured in the Telegram Mini App Store". TezMafia has both, so this is the highest-value free step. |
| 2 | Bot profile (BotFather) | `/setdescription`, `/setabouttext`, `/setuserpic`, description picture | Text and picture per language (at least uz, ru, en) | Free | Standard BotFather commands (not re-checked today). A weak profile also blocks Telegram Ads review: guidelines require a profile image and full description (VERIFIED, https://ads.telegram.org/guidelines). |
| 3 | TGStat | https://tgstat.ru , https://tgstat.uz | Channel `@TezMafia` once it has posts; category Games/Entertainment | Free to add (UNVERIFIED) | HTTP 403 to my fetch; submission rules NOT verified. The existing draft calls it a "bot catalog": I could not confirm that TGStat lists bots, treat it as a channel catalog. Whether tgstat.uz is a live localized catalog is UNVERIFIED. |
| 4 | Telemetr | https://telemetr.io | Channel, for analytics and rating | Free tier (UNVERIFIED) | HTTP 403, not verified. |
| 5 | Storebot | https://storebot.me | Bot username, description, category | Free listing; paid "featured" slots (a third-party blog quotes $200/mo category, $500/mo homepage: UNVERIFIED) | Connection refused from my machine. |
| 6 | DirectoryTG | search the name | Public bot or channel | Free per a vendor blog; review 1-5 days; needs 50+ subscribers (UNVERIFIED) | Re-check before use. |
| 7 | Bot lists: @BotsArchive, TG Bot List, TGFind | search each name | Bot username + short description | Mostly free | UNVERIFIED, names only. |
| 8 | Uzbek channel directories / "reklama" aggregators | manual search: "telegram kanallar katalogi O'zbekiston" | Channel | Varies | Not researched in depth; owner shortlists 2-3. |

There is no official Telegram bot directory (third-party summary, consistent with the docs). Skip paid "featured" slots
until rows 1-2 and a small Ads test have been done.

Preconditions before any submission:
1. `@TezMafia` has 10-15 posts (DECISION-18 plan) and a post in the last 2 weeks.
2. Bot profile texts and Main Mini App are set (rows 1-2).
3. No production numbers in any text (channel/README.md rule).

## 2. Submission kit (ready to paste)

Name: `TezMafia - Mafiya hakami` (uz) / `TezMafia - ведущий Мафии` (ru) / `TezMafia - Mafia host` (en).
Category: Games (or Entertainment / Board games where offered).
Keywords uz: mafiya, mafia o'yini, telegram o'yin, guruh o'yini, hakam bot, rollar, turnir, klan.
Keywords ru: мафия, игра мафия, ведущий мафии, бот для группы, игры в телеграм, турнир, кланы.
Keywords en: mafia game, telegram game bot, group game host, werewolf, party game, tournament.

### Short (max 120 chars)
- uz: `Guruhingiz uchun bepul Mafiya hakami: 21 rol, haftalik turnir, klanlar. Odam kam bo‘lsa — botlar to‘ldiradi.`
- ru: `Бесплатный ведущий Мафии для вашей группы: 21 роль, турниры, кланы. Мало игроков — места займут боты.`
- en: `Free Mafia host for your Telegram group: 21 roles, weekly tournament, clans. Few players? Bots fill the seats.`

### Long
**uz**
TezMafia — Telegram guruhlari uchun Mafiya o‘yinining avtomatik hakami. Botni guruhga qo‘shing, `/game` yozing: lobby ochiladi, rollar shaxsiy xabarda tarqatiladi, tun va kun o‘zi almashadi.
- 21 rol (16 tasini o‘chirib qo‘yish mumkin), 4 rejim, 5–23 o‘yinchi
- 5 kishi bo‘lmasa ham bo‘ladi: bo‘sh o‘rinlarni bot-o‘yinchilar to‘ldiradi
- Haftalik turnir, klanlar, reyting, 15 yutuq, natija kartalari
- Mini App: profil, yutuqlar, o‘yinlar xronikasi
- Adminlar uchun: rol to‘plami, taymerlar, anonim ovoz, `/kick`, `/ban`, guruh statistikasi
- 11 til

Hakam bepul. Olmos, belgilar, uslublar va pass — faqat bezak. Coin o‘ynab yig‘iladi (yoki Stars bilan olinadi) va o‘yin ichidagi buyumlarga ham sarflanadi.

**ru**
TezMafia — автоматический ведущий «Мафии» для групп Telegram. Добавьте бота в группу и напишите `/game`: откроется лобби, роли придут в личку, ночь и день сменяются сами.
- 21 роль (16 можно отключить), 4 режима, 5–23 игрока
- Нет 5 человек? Свободные места займут боты-игроки
- Еженедельный турнир, кланы, рейтинг, 15 достижений, карточки результата
- Mini App: профиль, достижения, хроника игр
- Для админов: набор ролей, таймеры, анонимное голосование, `/kick`, `/ban`, статистика группы
- 11 языков

Ведущий бесплатный. Алмазы, значки, стили и пропуск — только косметика. Монеты зарабатываются игрой (или покупаются за Stars) и тратятся в том числе на игровые предметы.

**en**
TezMafia is an automatic host for Mafia games in Telegram groups. Add the bot, type `/game`: the lobby opens, roles arrive in DMs, night and day switch on their own.
- 21 roles (16 can be switched off), 4 modes, 5-23 players
- Fewer than 5 people? Bot players fill the empty seats
- Weekly tournament, clans, rankings, 15 achievements, result cards
- Mini App: profile, achievements, game chronicle
- For admins: role set, timers, anonymous vote, `/kick`, `/ban`, group stats
- 11 languages

The host is free. Gems, badges, skins and the season pass are cosmetic. Coins are earned by playing (or bought with Stars) and also buy in-game items.

### Channel description (`@TezMafia`)
- uz: `Qorashahar xabarlari: Mafiya hakami botining yangiliklari, turnir g‘oliblari, rollar sirlari. Bot: @qorashahar_mafia_bot`
- ru: `Новости Корашахара: бот-ведущий Мафии, победители турнира, секреты ролей. Бот: @qorashahar_mafia_bot`
- en: `Qorashahar news: updates for the Mafia host bot, tournament winners, role secrets. Bot: @qorashahar_mafia_bot`

## 3. Assets (all exist in `assets/raven/`)

| Use | File |
|---|---|
| Square logo / avatar | `avatar.jpg` |
| Cover / banner | `banner.jpg` |
| Screenshot set (3-5) | `scenes/lobby.jpg`, `scenes/night.jpg`, `scenes/trial.jpg`, `scenes/win-town.jpg`, `scenes/roles-dealt.jpg` |
| Roles | `roles/mafia.jpg`, `roles/detective.jpg`, `roles/doctor.jpg` |
| Menu art | `menu/h01-start.jpg`, `menu/h04-profile.jpg`, `menu/h03-shop.jpg` |
| Skins | `skins/preview.jpg` |
| Mini App previews (Main Mini App media) | Real Mini App screenshots are NOT in the repo; the owner captures profile, ranking, shop on a phone |

Avoid `menu/h05-top.jpg` or any real leaderboard screenshot while synthetic data is still in the database
(channel/inventory.md "Do not post").

## 4. Could not verify
Every third-party catalog's current rules, prices and bot acceptance; tgstat.uz; exact BotFather menu labels;
channel description length limit.
