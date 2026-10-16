# TezMafia: referral boost proposal (not implemented)

## 1. What exists today (from the code)
- `/invite` (bot.py `cmd_invite`) shows a personal link `https://t.me/<bot>?start=ref_<userId>`, the number of people invited (`referral_count`, counts everyone who arrived, not only rewarded), and a share button.
- `/start ref_<id>` (`cmd_start`): `add_referral` accepts only brand-new users (no stats row, never referred) and not self-referral. The new user is told they get coins after their first game.
- Reward (`reward_referral`, `retention.py`): when the referred user finishes their first game, `take_referral` marks it paid atomically (once). Inviter +50 coins (`REF_INVITER_COINS`), newcomer +25 (`REF_NEW_COINS`). The inviter gets a DM.
- Condition in the game-finish flow (bot.py, around line 633-651): the payout is called only in the full tier (5+ humans) and only when `totals["games"] == 1`. In a game with bots the whole block is skipped (comment: "no farming").
- Inline mode has an invite card. Founder reward (200 coins, 2 gems, 🎖) is separate and for groups.
- No tiers, no leaderboard, no cap, no per-day limit, no link to the account's age or fair-play score. Invited count has no use beyond the display.

## 2. Observations / gaps
1. **Likely bug (needs a test, not verified at runtime):** if a referred user's first game is a bot-tier game (fewer than 5 humans), the referral block is skipped, and on their next game `games` is already above 1, so the reward may never be paid. This is exactly the small-group case TezMafia targets. Check `record_game`: whether `UserStat.games` increases in bot-tier games. If it does, fix by paying on the first FULL-tier game (e.g. `take_referral` without the `games == 1` condition).
2. The referrer reward is small (50 coins) relative to coin prices, and there is no milestone to chase.
3. Referral drives players, but the growth bottleneck is groups. Invitees alone cannot create games; the invite should say "bring your group".
4. No visible progress ("3 invited, 1 more to unlock...").

## 3. Anti-abuse principles (apply to any option)
- Pay only after the invitee finishes a first game with 5+ humans (already so; keep).
- Count a referral toward tiers only when it is "qualified": finished a full game AND fair-play score not reduced by AFK removal in that game. Pending invites count in the display only.
- Multi-account: newcomers must be brand-new Telegram users to the bot (already). Add: max 3 qualified referrals per inviter per 24 h for tier counting; hold rewards if the invitee played the first game only with the same group where the inviter is the only other human (sock-puppet pattern).
- Never pay in Stars or anything cashable; rewards are coins, gems, cosmetic badges. Coins already buy in-game items, so keep amounts modest and caps in place.
- Review: owner can see (new weekly digest line) qualified referrals and top inviters; revoke manually for obvious farms.
- Self-referral and circular referral (A invites B, B invites A) are blocked since B must be brand-new.

## 4. Tiered rewards: three options (owner chooses)
All tiers count qualified referrals (see section 3). The newcomer bonus stays 25 coins (option C raises it).

### Option A - Light (cheapest, least risk)
| Qualified invites | Reward (once per tier) |
|---|---|
| each | 50 coins (as now) |
| 3 | +100 coins |
| 10 | +1 gem |
| 25 | 🤝 badge "Recruiter" (earned-only, cosmetic; needs a new badge key) |
Total at 25 invites: 1,350 coins and 1 gem; cost small.

### Option B - Standard (recommended)
| Qualified invites | Reward |
|---|---|
| each | 50 coins |
| 1 | +1 gem (first-invite hook) |
| 3 | +150 coins + 🤝 badge |
| 10 | +3 gems + 300 coins |
| 25 | +8 gems + 700 coins + title "Qorashahar recruiter" on the profile/top |
Total at 25 invites: 1,250 + 150 + 300 + 700 = 2,400 coins and 12 gems (about a badge 👑). Gems are worth 20 per skin, so 25 invites is roughly half a skin: attractive but not game-breaking. Newcomer: 25 coins plus a first-game "welcome" chest of 25 more coins (50 total) to improve invite conversion.

### Option C - Group growth (aimed at groups, not individuals)
Same as B, plus: when an invitee's first full game happens in a group where the bot was added through the inviter's link (`startgroup` deep link with `?startgroup=ref_<id>`), the inviter gets +100 coins once per group (max 5 groups/person, same cap as the founder reward). Needs a payload format change in `my_chat_member` handling. Highest value for growth, most code.

Suggested decision: B now, C after B's anti-abuse proves stable for 2-4 weeks.

## 5. Leaderboard idea
- `/top` gets a "Recruiters" tab: monthly qualified referrals, top 10, with names/usernames as players already appear in `/top`. Monthly reset, 🏅 for the winner each month (cosmetic) plus 3/2/1 gems for top 3. Optional privacy: a profile setting to hide from the list.
- Weekly "recruiter of the week" line in the Monday channel post only with real numbers and only after synthetic data is cleaned (channel/README.md).
- Seasonal framing: tie the top tier to the November season pass (cosmetic skin at the highest tier would be a stronger hook, but the pass skin is currently the paid-track reward, so do not promise it without owner approval).

## 6. Messaging changes (copy, small code)
- `/invite` text: add progress ("Qualified: 2/3 -> next reward ...") and "bring your group" nudge with `startgroup` link.
- Post-game DM after a win with 5+ humans: one line, "Invite a friend: /invite". Max once per week per user.
- Channel post: explain tiers once the owner picks an option; wording "coins and gems; gems are cosmetic, coins also buy in-game items".

## 7. How to measure
Funnel: invite link opens, new users with `ref_`, qualified referrals, referral-to-group-added. Currently only `referrals` rows exist (user, referrer, time, rewarded). Add to the weekly digest: new referrals, qualified referrals, top 3 inviters (owner-only). Success metric: share of new users arriving via referral and their 7-day return, compared with non-referral users.

## 8. Not verified
Runtime behaviour of the bot-tier first-game case; whether `UserStat.games` counts bot-tier games; coin/gem valuations beyond the numbers in `channel/inventory.md`.
