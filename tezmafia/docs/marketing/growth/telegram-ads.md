# TezMafia: Telegram Ads plan

Owner owns the ads account and payment. Nothing here has been sent or purchased.

## 1. Goal
Primary: new groups that add the bot and finish a game (bot funnel: added, lobby, started, finished, repeat).
Secondary: cheap `@TezMafia` subscribers, only after 10-15 posts exist. Not a goal: raw /start count.

## 2. Platform facts
VERIFIED (https://ads.telegram.org/guidelines, https://ads.telegram.org/):
- Ad text max 160 characters including spaces. One button, one link; no button text limit is stated.
- Bots can be advertised and bot links may carry `start` parameters. One link in the text, no URL shorteners; main link and text link must lead to the same destination.
- The ad language must match the targeted channel's language (section 4.7): Uzbek ads to Uzbek channels, Russian to Russian.
- Promoted bots/channels need a profile image and full description; a channel needs a post in the last 2 weeks; bots must work properly on mobile and desktop.
- Gambling with real money/prizes is banned. TezMafia has no such mechanic; keep copy free of "win prizes/money".
- Official pages mention targeting by specific channels, and say private chats and contacts are not used. Payment is described as Gram (a cryptocurrency).

UNVERIFIED (third-party ad-tech blogs disagree; read the cabinet before budgeting):
- Minimum top-up: EUR 1,000-2,000, EUR 1,500, or a "EUR 2M threshold" for direct access with cheap entry through a TON cabinet from ~20 TON, or resellers from ~EUR 500 + VAT.
- Minimum CPM about EUR 1-2, first-price auction, effective CPM in entertainment about EUR 3-4.
- Topic (30+ categories), language and geo targeting, per vendors.
Sources: https://adsgram.ai/blog/adsgram/reklama-v-telegram-ads-v-2025-kak-zapustit-i-chto-eto , https://telegramadsanalytics.com/blog/how-to-advertise-on-telegram-2026

## 3. Audience and targeting
Start with hand-picked channel lists (checkable, context-matched), not broad topics.
| Segment | Ad language | Target channels (owner picks 15-30 by hand) |
|---|---|---|
| Uzbek youth, friend groups | uz | Uzbek entertainment, memes, student, game channels |
| Mafia / board-game fans | uz, ru | Mafia, werewolf, party-game, quiz channels |
| Russian-speaking Uzbekistan and CIS | ru | games, humor, student channels |
Use topic (Games, Entertainment) and language targeting only if the cabinet offers them, as a second ad group.
Exclude gambling/betting channels (policy risk, low intent). Prefer channels whose readers sit in group chats.
Region: Uzbekistan first (main market). Test CIS ru as a separate campaign so results stay readable.

## 4. Budget tiers (my assumptions, not promises)
Model: clicks = spend / CPM x 1000 x CTR. Assumed (UNVERIFIED): CPM EUR 3, CTR 0.5%, 30% of clicks press start, 15% of starters bring the bot into a group, 50% of those finish a game.
| Tier | Spend | Impressions | Clicks | Groups added | Groups that finish a game |
|---|---|---|---|---|---|
| Test | EUR 500 | ~165k | ~830 | ~35 | ~17 |
| Scale 1 | EUR 1,500 | ~500k | ~2,500 | ~110 | ~55 |
| Scale 2 | EUR 5,000 | ~1.7M | ~8,300 | ~375 | ~190 |
Real values can be 2-3x off either way. The test tier exists to measure CTR and cost per group. If the minimum top-up exceeds the test tier, the cheaper entry is a reseller or the TON cabinet (check fees first).
Run 3 creatives per language at equal budget for 3-5 days, then drop the weakest. Stop rule: pause when cost per finished-game group exceeds what the owner decides a group is worth (for example against group premium, 199 Stars/month).

## 5. Ad texts (max 160 chars, lengths checked by script)
**uz**
1. `Guruhda Mafiya o‘ynaysizmi? TezMafia hakamlik qiladi: rollar, tun, ovoz — hammasi avtomatik. Bepul.` (99)
2. `5 kishi yig‘ilmadimi? Bo‘sh o‘rinlarni bot-o‘yinchilar to‘ldiradi. TezMafia — Mafiya hakami, bepul.` (99)
3. `Qorashaharda tun tushdi. Kim mafiya? 21 rol, haftalik turnir, klanlar. Botni guruhga qo‘shing — bepul.` (102)
4. `Do‘stlar bilan Mafiya, lekin hakam yo‘qmi? Botni guruhga qo‘shing va /game yozing. 30 soniyada tayyor.` (102)
5. `Mafiya o‘yini endi telefonda, guruhda va o‘zbek tilida. Rollar shaxsiy xabarda, hakam — bot. Bepul.` (99)

**ru**
1. `Играете в Мафию в группе? TezMafia ведёт игру сам: роли, ночь, голосование. Бесплатно.` (86)
2. `Не набралось 5 человек? Свободные места займут боты-игроки. TezMafia — ведущий Мафии, бесплатно.` (96)
3. `Над Корашахаром опускается ночь. Кто мафия? 21 роль, турнир каждую неделю, кланы. Ведущий бесплатный.` (101)
4. `Мафия с друзьями, а ведущего нет? Добавьте бота в группу и напишите /game. Готово за 30 секунд.` (95)
5. `Мафия в Telegram-группе на 11 языках. Роли приходят в личку, ведёт игру бот. Бесплатно.` (87)

**en** (only for English-language channels)
1. `Playing Mafia in a group chat? TezMafia hosts it for you: roles, night, voting. Free.` (85)
2. `Not enough players? Bots fill the empty seats. TezMafia, a free Mafia host for your Telegram group.` (99)
3. `Night falls over Qorashahar. Who is the Mafia? 21 roles, weekly tournament, clans. Free host bot.` (97)
4. `Mafia with friends but nobody to host? Add the bot to your group and type /game. Ready in 30 seconds.` (101)
5. `Mafia in a Telegram group, in 11 languages. Roles arrive in DMs, the bot runs the game. Free.` (93)

Avoid in copy: "no pay-to-win", "Stars only buy cosmetics", user or game counts, prize or money promises.
Image: `assets/raven/banner.jpg` or a `scenes/` image; check the cabinet's required ratio (third parties say 16:9: UNVERIFIED).

## 6. Landing: bot or channel
Recommendation: the bot. The conversion that matters (adding it to a group) happens from the bot menu, which has "Guruhga qo‘shish".
Link: `https://t.me/qorashahar_mafia_bot?start=ad_uz1` (one payload per creative; start params are allowed per the guidelines).
Channel ads: later, as a separate campaign, once `@TezMafia` has 10-15 posts and a recent post. DECISION-18 notes channel promotion needs 1000+ subscribers in some placements (earlier research, not re-verified).
Do not use `?startgroup=true` as the ad link until tested; the guidelines only mention `start`.

## 7. KPIs and measurement
Today `/weekly` (owner only) shows groups added, lobbies, games started, finished, repeat groups. It has no traffic source.
- From the Ads cabinet: impressions, clicks, CPM, spend.
- From the bot: funnel change in the test window versus the 2 weeks before (rough lift; no attribution).
- Proposed small code change, NOT done (owner decides): store the `/start` payload (`ad_*`) at first contact so `/weekly` can show starts and groups added per creative. Today `cmd_start` handles only `ref_`, `app`, `g_`; other payloads just show the menu.
Test targets (confirm after 3 days): CTR at least 0.4%; cost per added group falling; at least 40% of added groups finish a game. Pause creatives with CTR under half of the best one.
Do not publish resulting numbers in the channel (channel/README.md rule).
