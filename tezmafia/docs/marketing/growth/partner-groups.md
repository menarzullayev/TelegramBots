# TezMafia: partner / host groups outreach kit

Owner (or a person the owner designates) sends all messages. Nothing has been sent. Do not mass-DM: ask in groups
only where the admins allow ads, and one message per group.

## 1. Whom to target
Priority order (a group converts if it already has chat activity and 5+ regulars):
1. Friend, class and university groups in Uzbekistan (uz/ru) with active chats: the bot works in any group, no integration needed.
2. Existing Mafia/Mafiya game groups and communities that still use manual hosts or older host bots (they already know the game).
3. Gaming, board-game, quiz and streamer chats (discussion groups of channels in those topics).
4. Admins of mid-size entertainment channels with a linked chat (offer a "Mafia night" event).
Skip: groups with spam/gambling content, groups under ~10 active members, groups where ads are banned by the rules.
How to find them: Telegram search for "mafia", "mafiya", "мафия" groups, and the channels chosen for ads (telegram-ads.md section 3).

## 2. What the admin gets (all exist in the code today)
- Free host: roles, night/day, voting automatic. No setup beyond adding the bot and giving it rights.
- **Founder reward:** the person who adds the bot gets 200 coins + 2 gems + the 🎖 "Asoschi" badge when the group plays its first game with 5+ humans. Once per group, max 5 groups per person (`social.py`: FOUNDER_COINS 200, FOUNDER_GEMS 2, FOUNDER_MAX_GROUPS 5, FOUNDER_MIN_PLAYERS 5). Important: the founder is recorded only when the bot is newly added to the group (chat-member event). If the bot is already in a group, there is no founder reward.
- **Bot players** when fewer than 5 humans: `/addbot [n]` or the "Bot qo‘shish" button. Rewards scale with humans (5+ full; 3-4 half XP/coins, no tournament points; 1-2 XP only).
- Admin tools: `/config` (modes, role set, timers, anonymous vote), `/schedule 21:00` (reminder and auto lobby), `/kick`, `/ban`, `/groupstats`, `/history`.
- **Group premium:** 199 Stars/month: day up to 180 s, night up to 120 s, group name on result cards, 3-month stats (`/premium`). Mention it as optional, never as a condition.
- Weekly tournament and clans give the group a reason to return.
Money wording: gems, skins, badges and the season pass are cosmetic; coins also buy in-game items. Never say "no pay-to-win".

## 3. Message templates (ready to paste)

### uz
```
Assalomu alaykum! Guruhingizda Mafiya o‘ynaysizlarmi? TezMafia — bepul avtomatik hakam: rollar shaxsiy xabarda, tun/kun va ovoz berish o‘zi ketadi, 21 rol. Odam yetmasa bot-o‘yinchilar to‘ldiradi.
Sinab ko‘rish: https://t.me/qorashahar_mafia_bot?startgroup=true — botni qo‘shib, /game yozing.
Guruhni qo‘shgan admin ilk to‘liq (5+ kishi) o‘yindan keyin 200 coin, 2 olmos va 🎖 belgi oladi.
```
Short version for a group chat (admin allowed ads):
```
Mafiya o‘ynaymizmi? Bepul hakam-bot: https://t.me/qorashahar_mafia_bot?startgroup=true — qo‘shing va /game yozing. Rollar, tun, ovoz — hammasi avtomatik.
```

### ru
```
Здравствуйте! Играете в Мафию в группе? TezMafia — бесплатный автоматический ведущий: роли приходят в личку, ночь/день и голосование идут сами, 21 роль. Не хватает игроков — места займут боты.
Попробовать: https://t.me/qorashahar_mafia_bot?startgroup=true — добавьте бота и напишите /game.
Админ, добавивший бота, после первой полной игры (5+ человек) получает 200 монет, 2 алмаза и значок 🎖.
```
Short:
```
Сыграем в Мафию? Бесплатный бот-ведущий: https://t.me/qorashahar_mafia_bot?startgroup=true — добавьте и напишите /game. Роли, ночь, голосование — всё автоматически.
```

### Follow-up (after they added the bot, uz / ru)
- uz: `Rahmat! Guruhda 5 kishi yig‘ilsa /game yozing; yetmasa /addbot. Savol bo‘lsa shu yerga yozing — adminlar uchun /config va /schedule 21:00 ham bor.`
- ru: `Спасибо! Когда соберётся 5 человек, напишите /game; не хватает — /addbot. Для админов есть /config и /schedule 21:00.`

## 4. Offer ideas (only things that exist)
- "Mafia night" event: admin sets `/schedule 21:00`, the bot sends the reminder and opens the lobby.
- Group wars via clans and the weekly tournament (`/tournament`).
- Premium trial is NOT offered by the bot today; do not promise one. (Proposal: owner may gift group premium manually, a code change would be needed. Not done.)

## 5. Rules
- One outreach per group; no repeat if ignored. Stop on "no".
- No claims about player counts, game counts or ratings (production numbers are off-limits).
- Keep the bot link as given; do not use shorteners.
- Founder reward is a thank-you for adding the bot; do not offer cash or Stars.

## 6. Tracking table (copy to a sheet)
| Date | Group name / link | Language | Size (approx.) | Admin contact | Channel found via | Message sent (uz/ru, short/long) | Reply | Bot added (Y/N) | First 5+ game (Y/N) | Played again (Y/N) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

Weekly review: compare "bot added" in this sheet with the owner's `/weekly` funnel (groups added, lobbies, started, finished, repeat) to see which partners really played.
Targets (suggested): 20 groups contacted per week, 25% add the bot, 50% of those finish a game.
