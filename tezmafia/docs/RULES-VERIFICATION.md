# Rules verification — all role / mode / item combinations (2026-10-16)

Goal: prove that what the engine does is what the players are told. Sources of "what players are told":
`role.*` and `item.*` strings (`locales/en.json`, `uz.json`), channel posts 12–18 and 28, `/help`, `channel/inventory.md`.
Engine under test: `tezmafia/engine.py`, `roles.py`. Nothing here touches production, Telegram or the database.

## Result in one table

| Check | Result |
|---|---|
| Rules matrix `tests/test_rules_matrix.py` | **1,268 tests**, all green (2 s) — see the breakdown below |
| Of which assert a documented discrepancy (marker `discrepancy`) | 43 tests, 23 distinct cases (D1–D23) |
| Fuzz, extended simulator, 1,000,000 games | **0 violations, 0 never-ending games** |
| Fuzz, original simulator (`--classic`), 200,000 games | 0 violations, 0 never-ending games |
| Engine bugs fixed (with regression tests that fail without the fix) | 2 |
| Full suite / `qa_gate` / `ruff` | 1,758 passed / 100/100 / clean |

Mutation check: 10 deliberate engine mutations (Executioner respecting the Doctor, Don no longer reading clean,
hobo immunity removed, shop shield also stopping hanging, Mayor weight 1, idle limit 3, stalemate limit/alive cap
off by one, Lucky removed, ties not detected) each make 2–23 matrix rows fail, so the rows really bite.

## 1. Extended simulator (`scripts/loadtest/sim.py`, `fuzz.py`)

`play(seed, extras=True)` (new; the default `play(seed)` keeps its old random stream, so the database generator is
unchanged). `fuzz` runs the extended version unless `--classic` is given. New coverage:

| Feature | How it is exercised | Invariants added |
|---|---|---|
| Bots (`add_bot`, `bot_night_moves`, `bot_votes`, `bot_lynch_votes`) | 0–N bots per table (60% of games have some, up to all seats but one), acting right after `begin_night` / `begin_voting` / `begin_lynch` like `App.enter_night` does | bots never act without a night role, never target themselves or the dead; a mafia bot never aims at / votes against / hangs its own faction while anyone else lives; detective bot never shoots on night 1; `humans()` never contains a bot; the game still ends |
| Kick (`kick`) | admin kicks a random living player (humans and bots) before the night actions, after they were submitted, during voting, during the trial (50%: the accused) | dead, no action, no pending vote against them, logged exactly once as `kick`, winner/phase consistent with the return value, still dead at the end |
| Idle removal (AFK) | the existing 15% non-acting rate plus pistol owners who never shoot | removed only if night-duty, not acting, idle ≥ 2 nights; nobody who acted keeps an idle count; non-duty players are never counted |
| Role tickets / loadout (`App.apply_role_tickets`, `apply_loadout`, mirrored: they live in `bot.py` and need the store) | 30% of games swap a human's role, 5% per shop item (no pistol for night roles, bots own nothing) | role multiset unchanged, faction matches role |
| Lobby (`leave`, `can_start`, `extend_lobby`) | a late joiner who never opened the bot; extend | `can_start` = `dm_pending`, `start()` raises, seats stay 1..n |
| Table settings | `mafia_resolve` (majority/unanimous/first), `reveal_on_death`, `first_phase` day-first | — |
| Save/restore | 15% per phase: `to_dict` → JSON → `from_dict`, then keep playing the restored object | round trip is exact |
| Host `/stop` (`cancel`) and post-game calls | 0.4% per night | every action / kick / leave / resolve is refused after the end and changes nothing |
| Hooker / trial | a blocked player voting; the dead or the accused confirming | refused |

`fuzz` also reports "notes" — behaviours that are legal today but need an owner decision (see D6, D7, D11).

### Numbers (seed range 0–999,999, 3,231 games/s on 24 cores, 310 s)

| | Extended (1,000,000) | Classic (200,000) |
|---|---|---|
| violations | **0** | 0 |
| never-ending (60-night cap) | **0** | 0 |
| average nights | 5.88 | — |
| games with bots / bot seats | 374,700 / 1,930,833 | — |
| games with kicks / kicks | 224,723 / 341,618 | — |
| role-ticket swaps played | 147,789 | — |

Winner distribution, extended: mafia 587,911 (58.8%) · town 199,330 (19.9%) · suicide 85,852 (8.6%) · draw 45,068
(4.5%) · maniac 31,937 (3.2%) · host `/stop` (no winner) 21,114 (2.1%) · snitch 15,973 (1.6%) · mage 7,724 ·
crook 2,558 · arsonist 2,533. Classic: mafia 56.5% · town 21.4% · suicide 9.1% · draw 6.3% · maniac 3.6% · snitch 1.6%.
(The draw share is higher than the 0.44% in `docs/LOADTEST.md` because that figure predates the stalemate rule; the
random players of the simulator are far more passive than people.) Notes seen: 76,040 games where a kicked player
was on the winning side (D11), 30,588 pistol-owner nights counted as idle (D7).

Bugs the simulator found (both fixed, with regression tests):

1. `resolve_lynch` reported a player who was **kicked while their trial was open** as hanged (`eliminated` = the
   kicked seat), 194 per 5,000 games. Fix: nobody is hanged if the accused is already dead.
2. A pistol owner who skipped a night and then fired kept a stale `idle_nights = 1` for good (the reset was skipped
   once the spent pistol ended their "night duty"). A Sergeant promoted to Detective afterwards could be removed as
   idle one night early. Fix: reset the counter for anyone who acted, before the duty test.

## 2. Rules matrix (`tests/test_rules_matrix.py`) — 1,268 tests

| Section | Rows | What it pins |
|---|---|---|
| 1. Lethal sources × victim kinds × {no protection, Doctor protecting} | 252 | Mafia, Don, Maniac, Executioner, Detective shot, pistol, Arsonist fire against 19 victim kinds: plain, Sergeant, Mayor, Suicide, Kamikaze, Lucky (fresh/spent), Enchanter, Traitor, Dervish (home/away), Doctor, Detective, Lawyer, and the shop items shield / vest / mask / forged papers / trial shield |
| 2. Hanging × victim kinds × {direct vote, trial} | 39 | who survives (Lucky, trial shield), Kamikaze blast, Suicide win, mask, night shield not working on the gallows |
| 3. Hooker blocks every night role; blocked cannot vote | 20 | |
| 4. Mafia kill resolution (majority / unanimous / first, Don, ties) and Doctor rules, day-banner texts | 38 | |
| 5. Reactive roles (Executioner vs Detective, Enchanter, Kamikaze, Traitor) | 7 | |
| 6. Information: Detective check table, Spy visitors/helper, Dervish, Informer, Swindler, Arsonist marks, Sergeant, pistol, idle removal | 104 | |
| 7. **Ordered pairs of night roles**: 15 variants (Mafia, Don, Executioner, Maniac, Detective check/shoot, Doctor, Hooker, Lawyer, Dervish, Spy, Arsonist mark/ignite, Swindler, Informer) × 206 ordered pairs × 3 scenarios (same target / A on B / mutual) compared with a rule-based spec: deaths, blocked list, Detective answer, Spy report, Informer hit, refusals | 619 | |
| 8. Day: vote tally and the Mayor, ties, trial yes/no, Lawyer cover, trial shield, secret mode | 27 | |
| 9. Win conditions × survivors: 66 explicit compositions + every multiset of ≤ 4 survivors over the 21 roles (12,650 combinations) against an independent rule statement + win flags | 75 | |
| 10. Stalemate boundaries: 2 vs 3 quiet rounds, 4 vs 5 alive, reset by a death or a kick, first call, parameters | 13 | |
| 11. Dealing for 5…23 players, 10/5/6 faction split, core vs 16 specials, switched-off roles, chaos | 60 | |
| 12. Kick, bots, simulator harness (incl. a negative test that plants a bug and expects the simulator to flag it) | 12 | |
| 13. Extra discrepancy rows | 2 | |

Reading the tests: row ids carry the discrepancy code (`D4:hobo_away>…`). A test marked `discrepancy` asserts the
CURRENT behaviour. Change the behaviour on purpose → change that test and its row below in the same commit.

## 3. Discrepancies and ambiguities — owner decisions needed

Order = suggested priority. "Text" = what players are told; "Engine" = what happens; the test asserts the engine.

| # | Text says | Engine does | Recommended resolution | Test |
|---|---|---|---|---|
| D3 | Dervish: "Whoever comes there, you'll see." | Computes `hobo_seen` as the seats of the night's Mafia victim, Maniac victim and protected player (not the visitors of *his* door) and **never delivers it**: it is not in the `resolve_night` result and no handler reads it. The role has no information power at all. | Implement as the Spy does (visitors of the door he chose, DM at dawn), or reword the role until then. Highest priority: a role sold in the channel does nothing. | `test_D3_…` |
| D1 | Lawyer: "gets one partner clear of the Detective's check." | The same cover also voids the **hanging** of the covered player the next day (vote and trial), and may be put on anyone, not only partners. | Keep it (it makes the Lawyer worth playing) and add it to `role.lawyer.*` + post 13, or restrict the cover to the check. | `test_D1_…` ×2 |
| D6 | Lucky: "Walks away from the first attempt on their life." | Also absorbs the first **hanging** and the first idle removal, not only night attacks. | Decide whether the gallows is an "attempt on life"; write it into `role.lucky.*` or limit to night attacks (`cause == "night"`). Big effect on trials. | `lucky` rows, `test_D6_…` |
| D5 | Arsonist: "Three lives burned and the Arsonist wins." | `arson_kills` counts every marked seat on ignition, including marks that were **already dead** (lynched/shot earlier). Three dead marks win the game with nothing burned. | Count only players alive at ignition (`before.alive`). One-line fix; left as is because it is a rules call. | `test_D5_…` |
| D20 | Executioner: "No protection stops the Executioner — except the Detective." Shop: separate "Bulletproof vest" for the Executioner. | The ordinary Night shield **and** a fresh Lucky One both stop the Executioner's bullet (the vest then has no unique role). | Decide: shield/Lucky do not stop him (matches the text and gives the vest a purpose), or reword the Executioner. | `shield>killer`, `lucky>killer` |
| D2 | Not mentioned. | The Don reads "civilian" to the Detective (only a test asserts it). | Add to `role.don.*` and post 13, or remove. | `D2:don-looks-clean` |
| D7 | Pistol: "you fire once, at night." (optional) + "a night role that sits idle for 2 nights is out of the game." | A pistol owner counts as having night duty: not shooting for two nights removes them as idle. | Exempt pistol owners from the idle rule, or say so in `item.gun.desc`. | `test_D7_…` |
| D11 | — | A kicked player on the winning side is paid as a **winner** (`record_stats` uses `player_won`, which ignores how they left). `kick` sets no `last_death_*`; the bot's last-words invite after a trial then goes to the stale `last_death_seat` (the night's victim). | Exclude `cause == "kick"` from winners/rewards; invite last words from `result["eliminated"]`. | `test_D11_…` |
| D4 | Dervish: "Your own place stays empty." | A Dervish who went to someone else is **immune** to every targeted kill (Mafia, Maniac, Executioner, Detective shot, pistol, fire; the day text then says "the Mafia missed"); and a Dervish sleeping at a victim's door **dies with the victim**. Neither is written anywhere. | Document both (the immunity is a sensible reading of "empty") or drop the witness death. | `D4:hobo_away>…` (7 rows), `test_D4_…` ×2 |
| D14 | Executioner: "No protection stops the Executioner." | The Dervish's empty house does. | Covered by D4's decision; say "except the Detective and an empty house". | `D14:hobo_away>killer` |
| D16 | Day messages: who died / "saved". | `texts.day_group` shows one line: the "miss" or "saved" banner hides a real death (Maniac kill on a night the Mafia had no target; Mafia victim saved but the Executioner killed him anyway), and with two deaths only the last is named. `night_deaths` has them all. | Build the dawn text from `night_deaths`. | `test_D16_…` ×3 |
| D17 | Detective: investigates / shoots, one per night. | A Detective killed earlier the same night still gets the answer and **still shoots** (the shot lands), while a dead Executioner, Arsonist or pistol owner does not act (D21). | Make it uniform: either all attackers act simultaneously, or a dead attacker never acts. | `test_D17_…`, `test_D21_…` |
| D21 | — | Mafia/Maniac hits resolve first; a dead Executioner/Arsonist/pistol owner then does nothing, but a dead Detective shoots. | See D17. | `test_D21_…` |
| D9 | Enchanter: "Whoever raises a hand against the Enchanter at night dies instead." | The reflected bullet kills the **first Mafia/Don by seat**, not the player who voted for that target. | Reflect onto the Don if he voted, else the first voter. | `test_D9_…` |
| D10 | Kamikaze: "takes one of those who voted for it." | Always the **first voter by seat**; the blast ignores Lucky / shields / Enchanter of that voter. | Pick randomly among voters, or let the Kamikaze choose; document that protections do not apply. | `test_D10_…`, `kamikaze` rows |
| D8 | Mayor: "At the trial, the Mayor's one vote counts as two." | Double only in the nomination vote; the yes/no confirmation counts him once. | Clarify "trial" in posts 15 / `role.mayor.*` (nomination), or apply the weight to the confirmation. | `test_D8_…` |
| D15 | Swindler: "tomorrow they vote for whoever you want." | Can force the victim to vote for **themselves** (impossible through `/vote`), and stolen Mayor weight doubles the Swindler's target (Mayor victim + own vote = 3). | Forbid self-votes in the steal; decide on the Mayor combo. | `test_D15_…` |
| D12 | Lover: "they make no move tonight." | Two Lovers picking each other: the lower seat blocks first, the other is then blocked and does nothing (order, not choice). | Resolve both blocks simultaneously (both blocked) or document seat order. | `test_D12_…` |
| D22 | Lover: "can't vote the next day." | Only the nomination vote is blocked; the blocked player may still confirm the hanging (yes/no). | Block both, or document. | `test_D22_…` |
| D13 | Town: "when no enemies are left." Informer: "same target as the Detective." | A lone **Suicide** survivor gives the **Town** the win (town members are dead); a lone **Informer** (or Informer + civilians) never ends the game — only the stalemate draw can. | Lone Suicide: Suicide loses/draw; lone Informer: count as non-enemy for the town win. | `D13:lone-suicide…`, `D13:lone-informer…` |
| D18 | Informer: "If the Informer guesses who the Detective is investigating, the game ends — in the Informer's favor." | Wins even if killed the same night. | Fine as is; mention "even posthumously" if it matters. | `test_D18_…` |
| D19 | Executioner: "Just don't aim at the Detective — you'll be the one who dies." | Also dies when the Detective was killed by the Mafia earlier that night. | Fine / document. | `test_D19_…` |
| D23 | Doctor: "Pulls one person back from death every night." | Cannot stop the Arsonist's fire (only the Executioner is documented as ignoring protection). | Add to `role.doctor.*` / `role.arsonist.*`. | `test_D23_…` |

Not a discrepancy but worth knowing: from 18 players up no plain Civilian is dealt (post 18 only promises them at
"small and mid-sized tables"); `bag_for(n)` and the 5…23 table match the unlock list in `channel/inventory.md`.

## 4. Not covered here

- `bot.py` layers: role-ticket payment/refund and loadout purchase are mirrored in the simulator (`apply_role_tickets`
  swap logic, `apply_loadout` gun rule) but not integration-tested; reward tier (`reward_tier`) is outside the engine.
- Rendering of the texts (localised strings) beyond the three day-banner checks in D16.

## 5. Reproduce

```bash
BOT_TOKEN=0000000000:AAFakeTokenForCiOnlyNotReal DATABASE_URL='sqlite+aiosqlite:///:memory:' PYTHONUTF8=1 \
  pytest -q -p no:warnings tests/test_rules_matrix.py          # 1,268 tests, ~2 s
  pytest -q -p no:warnings tests/test_rules_matrix.py -m discrepancy   # the 43 decision rows
python -m scripts.loadtest.fuzz --games 1000000                # extended simulator
python -m scripts.loadtest.fuzz --games 200000 --classic       # original simulator
```
