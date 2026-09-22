# Research — Telegram Serverless vs TezMafia cost

**Date:** 2026-09-22  
**Question:** Serverless yoqilsa, TezMafia server xarajati nolga tushadimi?  
**Answer:** **Yo‘q — hozirgi referee bilan yo‘q. Oddiy update-driven bot uchun VPS ijarasi yo‘qolishi mumkin, lekin narx kafolati yo‘q va TezMafia timerlari platformada yo‘q.**

**Decision:** [DECISION-10](decisions/DECISION-10-serverless-stay-python.md) **A** — production Python qoladi; JS rewrite yo‘q.

Primary source: [Telegram Serverless](https://core.telegram.org/bots/serverless) (fetched 2026-09-22).  
CLI: `@tgcloud/cli` 0.1.2.  
Live bot: `@qorashahar_mafia_bot` id `8818552086` (same `app` prefix as BotFather CLI token).

Secrets (CLI access token, bot token) are **not** recorded here.

## What Telegram Serverless is

Official model:

- JavaScript modules in a V8 isolate on Telegram infrastructure.
- Entry points are `handlers/<update_type>.js` — one file per Bot API update type.
- Loop: update arrives → handler runs → talks to `api` / `db` / `fetch` → **returns**.
- Platform manages the webhook (`npx tgcloud webhook`). `getUpdates` and webhook are mutually exclusive ([Bot API](https://core.telegram.org/bots/API)).
- Built-in SQLite (`schema.js` + Drizzle-like `db`). No foreign keys (`PRAGMA foreign_keys` off).
- Runtime: **no npm packages, no filesystem**, network only via SDK `fetch`.
- Files: send/forward by `file_id` OK; **download bytes and upload new files from a handler are not supported yet**.
- Outbound HTTP: textual bodies, **32 MB** response cap (CLI help also said 30 MB — treat as ~30–32 MB).
- CLI token is **not** the Bot API token (`app<id>:<secret>`; `TGCLOUD_TOKEN` or `.tgcloud/credentials`).

Documented day-to-day commands: `push`, `migrate`, `run`, `status`, `webhook`.

## What the official page does **not** say

Searched the primary page (2026-09-22): **no pricing, no free-tier, no CPU/memory quota, no invocation timeout, no cron/alarm/scheduled-handler API.**

Secondary write-ups (HN, ReasonCore) repeat the same gap. Those are not primary sources.

## Measurement (this host, 2026-09-22)

| Check                                       | Result                                                                                   |
| ------------------------------------------- | ---------------------------------------------------------------------------------------- |
| BotFather Serverless enabled                | yes (CLI token accepted for `app8818552086`)                                             |
| `tezmafia.service`                          | **active**, PID **1840047**                                                              |
| `getWebhookInfo`                            | **url empty**, pending **0**, last error empty                                           |
| `allowed_updates` (polling)                 | `message`, `callback_query`                                                              |
| `npx tgcloud webhook`                       | url unset, pending 0, in sync                                                            |
| `npx tgcloud add handlers` advertised types | Bot API update types only (message, callback_query, poll, chat_member, …, `managed_bot`) |
| `cron` / `schedule` as handler names        | **rejected** (invalid)                                                                   |
| `tgcloud push`                              | **not run**                                                                              |

Enabling Serverless in BotFather **did not** attach a webhook. Polling still owns updates. The first `push` / `webhook sync` would.

## TezMafia contract (already decided)

[DECISION-01](decisions/DECISION-01-runtime-topology.md): single systemd process, `App.lock`, in-memory `Game` + sqlite snapshot, **long polling**, no Redis/webhook/Postgres.

Phase clock is in-process (`App.schedule` → `asyncio.sleep` → `_timed_*`): night 45s, day 90s, vote 45s, lynch 25s, lobby 180s, plus AFK (2 idle nights) and DECISION-08 recover grace.

Night mute means the group is silent during the phase that most needs a timer.

## Cost question — facts vs not-facts

| Claim                                                              | Verdict                                                                      |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Telegram hosts JS handlers so you need no VPS for _those handlers_ | **Fact** (docs: “no machine to rent”)                                        |
| That hosting is free forever / $0 SLA                              | **Not a fact** — unpublished                                                 |
| TezMafia as-is (Python, polling, `asyncio` timers) can run there   | **False**                                                                    |
| TezMafia-equivalent game can run _only_ on Serverless              | **Not shown** — no scheduler; muted night has no incoming group updates      |
| Current TezMafia incremental VPS bill                              | **Already ~$0** — `tezmafia.service` on this host, not a dedicated VPS       |
| First production `tgcloud push` is free of product risk            | **False** — webhook replaces polling; live referee stops seeing `getUpdates` |

Lazy “advance phase on next update” is not a substitute: night is muted; AFK tables can have zero DMs; lobby expire and recover grace are time-based.

A second always-on ticker (Cloudflare cron, another VPS, a user-account scheduled message) is **another vendor**, not “Telegram Serverless alone”, and still not a published $0.

## Isolate timer measurement (`npx tgcloud run`, no push)

| Mechanism                                         | 2s           | 15s+         | Notes                                          |
| ------------------------------------------------- | ------------ | ------------ | ---------------------------------------------- |
| `setTimeout`                                      | fail 2–3ms   | fail         | `ReferenceError: setTimeout is not defined`    |
| CPU busy-wait                                     | ok (~2004ms) | fail ~3003ms | `Terminated: CPU timer exceeded` (~3s CPU cap) |
| `Atomics.wait`                                    | ok (~2017ms) | fail ~11s    | `Script execution failed`                      |
| `setInterval` / `queueMicrotask` / global `fetch` | —            | —            | undefined (use SDK `fetch` only)               |

**Conclusion:** a handler cannot implement night 45s / day 90s internally.

Bot API `sendMessage` has **no** `schedule_date` for bots (user-account MTProto scheduled messages are a different API).

## Timer alternatives (not “Serverless alone”)

| Approach                                                                                   | Works?            | Cost / lock-in                                                   |
| ------------------------------------------------------------------------------------------ | ----------------- | ---------------------------------------------------------------- |
| Sleep inside handler                                                                       | **No** (measured) | —                                                                |
| Lazy: advance phase on next update                                                         | Partial           | Night mute + AFK = no updates → phase stuck                      |
| External ticker → Telegram update (second bot, user `/tick`, CF/GitHub cron `sendMessage`) | Yes, in principle | Second vendor; not published $0; DECISION-01 clock moves off-box |
| Product change: only `/next` / “all acted”                                                 | Yes               | Game rules change vs TrueMafia/MafiaAz timers                    |

## Rewrite surface (if JS separate project)

Python package today: `bot.py` (~1.3k lines) + `engine` / `roles` (21) / `shop` / `mute` / `recover` / 11×223 i18n + QA 100. Runtime on Serverless: **no npm** (no telegraf/grammY), no file upload, concurrent isolates (no `App.lock`), sqlite without FKs.

Same-bot cutover **requires** stopping polling (webhook exclusive). A **new** bot can run JS while Python stays on `@qorashahar_mafia_bot`.

## If someone still prototypes

Use a **throwaway BotFather bot**, never `@qorashahar_mafia_bot`.

Do **not** `tgcloud push` or `webhook sync` on the live bot while DECISION-01 polling is production.

## Sources

- https://core.telegram.org/bots/serverless
- https://core.telegram.org/bots/API (getUpdates vs setWebhook)
- https://www.npmjs.com/package/@tgcloud/cli (0.1.2)
- Live: `getMe` / `getWebhookInfo` / `systemctl --user` / `npx tgcloud` (read-only)
