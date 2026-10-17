# TezMafia — instructions for Claude (local and cloud sessions)

Telegram Mafia game host bot (@qorashahar_mafia_bot), noir "Qorashahar" world, 11 languages, Mini App at
https://mafia.bugvector.uz, news channel @TezMafia. Owner: **Saidakbar aka**.

## Talking to the owner

- Always address him as **Saidakbar aka**. Reports, questions and explanations in **Uzbek (Latin)**.
- Code, commands, paths, commits and PRs stay in English. Raw errors are quoted as-is, then 1–2 lines in Uzbek.
- Answer first, then context. End with a 3–5 line summary. Decisions with real trade-offs go through
  AskUserQuestion; obvious defaults are taken and stated.
- Never claim "done" without measuring: run the tests, check the real output, verify production after deploy.

## Layout

- `tezmafia/` — the bot (Python 3.12, aiogram 3, SQLAlchemy async + aiosqlite, single process, long polling).
  - `engine.py` game rules · `bot.py` handlers/App · `db.py` Store · `webapp/` Mini App (aiohttp, served by the bot)
  - `locales/*.json` — 11 locales: uz en ru az br id kg kz tj tr ua (uz is the source; o‘ g‘ ‘ apostrophes)
  - `scripts/` — load tests (`loadtest/`), channel publishing, Windows supervisor and auto-deploy (`windows/`)
  - `docs/decisions/DECISION-*.md` — accepted decisions; read the relevant one before changing a feature.
  - `docs/RULES-VERIFICATION.md` — rules matrix and the open rule discrepancies (D1–D23) awaiting the owner.
- Other folders in the repo (`tezmath/`, `GenderAnalyzerBot/`) are separate projects — leave them alone.

## Commands (run from `tezmafia/`)

```bash
pip install -e ".[dev]"
BOT_TOKEN=0000000000:AAFakeTokenForCiOnlyNotReal DATABASE_URL='sqlite+aiosqlite:///:memory:' pytest -q -p no:warnings
python -m tezmafia.qa_gate          # must stay 100/100
ruff check tezmafia tests scripts
```

On the owner's Windows PC the interpreter is `.venv-win/Scripts/python.exe` (pytest/ruff next to it).

## Rules for changes

- New user-facing strings go into **all 11 locales**, written with a script using
  `json.dumps(data, ensure_ascii=False, indent=2) + "\n"`. The QA gate checks key parity and placeholders.
- Every new check or rule gets a **negative test** proving it catches the bad case (fails without the fix).
- Comments in English, only where the code is not obvious. Match the surrounding style.
- Commits: Conventional Commits (`fix(referral): ...`), English.

## Git, CI and deploy

1. Branch from `origin/main` → commit → push → PR (`gh pr create`).
2. CI (`TezMafia CI`, check `pytest + QA gate`, GitHub-hosted ubuntu) must be green.
3. The owner pre-authorized merging **your own** PR once CI is green: `gh pr merge N --squash --delete-branch`.
   Never merge red or pending CI.
4. **Deploy is automatic**: the "TezMafia AutoDeploy" task on the production PC (`scripts/windows/autodeploy.py`)
   pulls `origin/main` within ~2 minutes once its CI is green, restarts the bot and checks `/health`; it DMs the
   owner on failure. Do not try to reach the PC.
5. Verify: `curl -s https://mafia.bugvector.uz/health` must report the merged commit (short sha) within ~3 minutes.
   Report the commit in your answer. If it does not appear, stop and tell the owner.

## Production facts

- Runs on the owner's Windows PC (`D:\Linux\TelegramBots`), started by the supervisor (`scripts/windows/supervisor.py`),
  SQLite DB in `tezmafia/data/`, logs in `tezmafia/data/logs/`. Only that machine sets `TEZMAFIA_PRODUCTION=1`.
- The DB currently holds **synthetic load-test data** (1M users/games). It is wiped before the public launch;
  until then `NEWS_CHANNEL` stays off. Never post statistics from it anywhere public.

## Never

- **Never run the bot** (`python -m tezmafia`) outside production and **never set `TEZMAFIA_PRODUCTION`** in a
  cloud or dev environment: a second poller with the real token knocks the live bot off Telegram (409 Conflict).
  The bot refuses to start without the flag; do not work around it.
- Never print, log or commit secrets (`BOT_TOKEN`, `.env` contents). Tests use the fake token above.
- Never send messages or posts to the public channel, groups or users without the owner's explicit permission.
- Never spend Telegram Stars, buy anything, or touch payments. Never enter passwords or solve CAPTCHAs.
- Never delete data, force-push or rewrite `main`.
