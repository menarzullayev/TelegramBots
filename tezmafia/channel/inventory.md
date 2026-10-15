# Launch series inventory (63 posts)

Built from PRs #1, #3–#29, `docs/`, `locales/uz.json` and the `bot.py` handlers. Commands are verified
against the code; button labels are the real `btn.*` strings. Asset paths are relative to `assets/raven/`.

Assets: `avatar.jpg`, `banner.jpg`; `scenes/` lobby, roles-dealt, night, dawn, dawn-death, trial,
verdict-confirm, verdict-sealed, win-{town,mafia,maniac,suicide,arsonist,snitch,mage,crook};
`roles/` (21): arsonist citizen crook detective doctor don hobo hooker journalist kamikaze killer lawyer
lucky mafia mage maniac mayor sergeant snitch suicide werewolf; `menu/` h01-start h02-help h03-shop
h04-profile h05-top; `skins/{noir,gold,neon}/<role>.jpg`, `skins/preview.jpg`; stickers are .webp (not
usable as rich photos).

## A. Onboarding
| # | Title | Seg | Shows | Commands / buttons | Visual |
|---|---|---|---|---|---|
| 1 | TezMafia: a free Mafia host for your group | player | What the bot does; roles, night/day, voting all automatic | `/start`, `Guruhga qo‘shish` | banner.jpg |
| 2 | Meet the Raven of Qorashahar | player | Mascot, noir world, brand voice | — | avatar.jpg |
| 3 | Add the bot in 30 seconds | admin | Add link, welcome message, admin-rights hint | `Guruhga qo‘shish` (?startgroup=true) | scenes/lobby.jpg |
| 4 | Your first game | player | `/game` → `Men o‘ynayman` → `O‘yinni boshlash` (grey until n/5) | `/game` `/mafia` `/newgame` `/join` | mock |
| 5 | Why press /start in the bot first | player | Roles arrive in DM; lobby marks who isn't ready | `/start` | menu/h01-start.jpg |
| 6 | Night falls: the phase cycle | player | Night → dawn → discussion → trial → confirm | `Ha — osilsin` / `Yo‘q — yashasin`, `Fikrimdan qaytdim`, `/vote N`, `/action N` | slideshow night, dawn, trial, verdict-confirm |
| 7 | Who wins? 8 endings | player | Win conditions (town, mafia, maniac, suicide, arsonist, snitch, mage, crook) + draw | `/help` | slideshow 8 × scenes/win-* |
| 8 | Live countdowns and table control | player | Timers in the reader's language; extend/skip | `/extend` `/next` `/status` `/leave` `/stop` | mock |
| 9 | The "Rolim" button | player | Your role as an ephemeral message only you see | `Rolim` | mock |
| 10 | Final table of all roles | player | Rich-message summary table at game end | — | mock |
| 11 | 11 languages, one tap | player | uz ru en ua kz kg tj az tr id br; profile follows the user's language | `/settings` `/lang` | menu/h02-help.jpg |

## B. Roles (21 total; 16 special can be switched off, 5 core locked)
| # | Title | Shows | Visual |
|---|---|---|---|
| 12 | 21 roles: who is who? | Role catalogue (`/roles`, `Kim kim?`) | slideshow of several roles |
| 13 | The Mafia family | Mafiya, Don, Qora advokat (lawyer), Jallod (killer), Josus (journalist) | slideshow mafia, don, lawyer, killer, journalist |
| 14 | The law: investigators | Komissar, Serjant, Darvesh (hobo) | slideshow detective, sergeant, hobo |
| 15 | Protectors and power | Doktor, Omadli (lucky), Hokim (mayor, vote counts twice), Oshiq (hooker) | slideshow doctor, lucky, mayor, hooker |
| 16 | Lone wolves | Manyak, Afsungar (mage), Firibgar (crook), Arsonist | slideshow maniac, mage, crook, arsonist |
| 17 | Tricksters | Suitsid, Ayg‘oqchi (snitch), Sotqin (werewolf), Kamikadze | slideshow suicide, snitch, werewolf, kamikaze |
| 18 | Tinch aholi: the most important role | Citizens decide trials | roles/citizen.jpg |

Role names and descriptions: take them from `locales/uz.json` (`role.*` keys) — do not invent abilities.

## C. Group admins
| # | Title | Shows | Commands | Visual |
|---|---|---|---|---|
| 19 | The /config panel | Mode, role reveal, night mute, day/night timers | `/config` | mock |
| 20 | 4 modes | Klassik / Xaos / Sirli / Tezkor | `/config` | scenes/roles-dealt.jpg |
| 21 | Your own role set, free | Switch off any of 16 special roles; core stay | `/config` → `Rollar` | mock |
| 22 | Anonymous vote | Only "voted N/M" until the vote closes | `/config` → `Anonim ovoz` | scenes/trial.jpg |
| 23 | Scheduled games | Reminder button; DM 15 min before; lobby opens itself | `/schedule 21:00`, `/schedule off`, `Eslatib qo‘y` | mock |
| 24 | Moderation | Kick from a game, bot-level ban | `/kick` (reply or seat) `/ban` `/unban` | mock |
| 25 | Group stats and history | Finished games, winners, monthly top 5, last 5 games | `/groupstats` `/history` | mock |
| 26 | Rights the bot needs | Restrict, pin, delete messages — and why | — | mock |
| 27 | Founder reward 🎖 | First 5+ player game in your group: 200 coins + 2 gems + badge | automatic | avatar.jpg |
| 28 | Fewer than 5? Add bots | Robot-N players; rewards scale with real people (5+ full, 3–4 half XP/coins, 1–2 XP only) | `/addbot [n]`, `Bot qo‘shish` | mock |
| 29 | Fair play and AFK | Rating 0–100, −15 when removed for AFK | `/profile` | mock |

## D. Progression and social
| # | Title | Shows | Commands | Visual |
|---|---|---|---|---|
| 30 | Your profile | Level, XP, achievements, fair play | `/profile` | menu/h04-profile.jpg |
| 31 | 15 achievements | List from `ach.*` in uz.json | `/profile` | mock |
| 32 | Legends of Qorashahar | Season, group and all-time ladders | `/top`, `Mavsum` / `Guruh` / `Hamma vaqt` | menu/h05-top.jpg |
| 33 | Daily bonus and streaks | 10 coins +5 per day (max 40), gem on day 7 | `/daily` | mock |
| 34 | Daily quests | 3 quests, 15 coins + 10 XP each, +1 gem for all three | `/quests` | mock |
| 35 | Invite friends | +50 coins for you, +25 for the friend after their first game | `/invite` | mock |
| 36 | Last words and the room of the dead | 90 s for a last message; the dead chat together | (DM flow) | scenes/dawn-death.jpg |
| 37 | Play again | New lobby in one tap; previous players get a DM | `Yana o‘ynash` | scenes/win-town.jpg |
| 38 | Result cards and sharing | 1280×720 card, share via inline mode | `Ulashish`, inline `@qorashahar_mafia_bot` | mock |
| 39 | Clans | 100 coins to create, up to 30 members | `/clan create|join|leave|top` | mock |
| 40 | Weekly tournament 🏆 | Win 3 pts, game 1 pt; Monday top 3 get 5/3/2 gems + 🏆 | `/tournament` | mock |
| 41 | The game chronicle | Death timeline with revealed roles (Mini App "O‘yinlarim") | `/app` | mock |
| 42 | Raven sticker pack | 8 stickers, t.me/addstickers/raven_by_qorashahar_mafia_bot | — | avatar.jpg |
| 43 | Mini App tour | Profile, achievements, ranking, shop, my games | `/app` | mock |

## E. Economy and payments
| # | Title | Shows | Commands | Visual |
|---|---|---|---|---|
| 44 | Qora bozor: the coin shop | +10 per game, +25 and a gem per win; in-game items | `/shop` `/buy niqob`, `/buy role komissar` | menu/h03-shop.jpg |
| 45 | Coin packs for Stars | 25⭐→100 · 100⭐→450 · 250⭐→1200 · 500⭐→2600 coins | `/shop` | menu/h03-shop.jpg |
| 46 | VIP | 150⭐ for 30 days: +50% coins and 💎 mark | `/shop` → VIP | mock |
| 47 | Gem badges | ⭐3 🌹5 💀5 🔥8 👑12 gems; 🏆🎖🎟 earned only | `/shop` → `Olmos do‘koni` | mock |
| 48 | Role-card skins | Noir / Oltin / Neon, 20 gems; role DM + result card | `/skins` | skins/preview.jpg |
| 49 | Group premium | 199⭐ a month: day up to 180 s, night up to 120 s, group name on cards, 3-month stats | `/premium` | mock |
| 50 | Season pass teaser | Starts with the November 2026 season; free + paid track | `/pass` | skins/preview.jpg |
| 51 | Season pass launch (1 Nov) | 20 tiers × 100 XP; 99⭐ paid track; skin at 10, 🎟 at 20 | `/pass` | mock |
| 52 | Safe payments | Stars only, invoice in DM, refunds through support | `/terms` `/paysupport` | none |
| 53 | Your data, your choice | Privacy policy, delete-my-data with confirm | `/privacy` `/deletemydata` | none |

## F. Behind the scenes
| # | Title | Shows | Visual |
|---|---|---|---|
| 54 | Built on Bot API 10.x | Ephemeral message, DisabledButton, live timers, rich tables | mock |
| 55 | 1M users, 1M games: the load test | Synthetic database; before/after (active-game lookup 1,560 ms → 3 ms; Mini App 28 → 171 req/s; 1000 parallel groups: 0 DB errors, 0 lost stats) | none |
| 56 | 1,000,000 games, 0 rule violations | Fuzzing; found and fixed the "everyone dead" draw and the lone arsonist | scenes/win-arsonist.jpg |
| 57 | Ending stalemates | 3 rounds without a death and ≤4 alive → draw | scenes/verdict-sealed.jpg |
| 58 | Games that don't freeze | Per-chat locks, self-healing timers, watchdog, crash recovery | none |
| 59 | 437 tests and a 100/100 QA gate | CI, linting, negative tests | none |
| 60 | 11 languages done properly | Placeholder parity tests; profile per language | menu/h02-help.jpg |
| 61 | How the Raven was drawn | Approved stages; 63 skins rendered by script | skins/preview.jpg |
| 62 | Mini App under the hood | Signed login (max 24 h old), rate limit 10 writes/min, 171 req/s | none |
| 63 | What's next | Season pass, new art, community | banner.jpg |

## Facts worth quoting
21 roles (16 switchable, 5 core) · 5–23 players · 11 languages · 4 modes · 15 achievements ·
XP: 10 per game, +20 win, +5 survive · coins +10 per game, +25 and 1 gem per win · packs 25/100/250/500⭐ →
100/450/1200/2600 coins · VIP 150⭐/30 days · badges 3–12 gems · skins 20 gems · clan 100 coins, 30 members ·
group premium 199⭐/month · season pass 99⭐, 20 tiers, from November 2026 · daily bonus 10 +5/day (max 40),
gem every 7th day · referral 50/25 · tournament 5/3/2 gems + 🏆 · founder reward 200 coins + 2 gems + 🎖 ·
437 tests, QA gate 100/100 · load test 1,000,005 synthetic users / 1,000,010 games · 1M fuzzed games, 0 violations ·
Bot API 10.3 · Mini App https://mafia.bugvector.uz

## Do not post
Owner-only commands (`/weekly`, `/refund`, funnel tab, alerts); production counts and leaderboards
(synthetic data present until cleanup); infrastructure (home PC, tunnel, ids, ports, paths); load-test weak
spots as marketing; "Stars only buy cosmetics" (false); unverified payment flows as tested; internal process.
