# TezMafia

Production Telegram Mafia engine: group is public table, DM is private role/action channel, bot is the only referee.

- Bot: [@qorashahar_mafia_bot](https://t.me/qorashahar_mafia_bot)
- Stack: Python 3.12, aiogram 3, SQLAlchemy + aiosqlite
- Runtime (**DECISION-01**, **DECISION-10**): bitta process, `App.lock`, sqlite snapshot, long polling — Redis/webhook/Postgres/Serverless yo‘q
- Sprint (**DECISION-13**): feature freeze — faqat bugfix/regressiya (`docs/decisions/`)
- Rules: 21 playable roles (TrueMafia 13 + MafiaAz extras), night-first, commissar check/shoot, plurality + lynch, reveal on death

## Run

```bash
cd /home/nsn/Workspace/TelegramBots/tezmafia
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # token stays local, never commit
.venv/bin/pytest
.venv/bin/tezmafia
```

systemd (user):

```bash
mkdir -p ~/.config/systemd/user
ln -sf /home/nsn/Workspace/TelegramBots/tezmafia/systemd/tezmafia.service ~/.config/systemd/user/tezmafia.service
systemctl --user daemon-reload
systemctl --user enable --now tezmafia.service
```

## Group setup

1. Add the bot to a public/supergroup.
2. Promote it: restrict members, pin, delete messages.
3. `/game` (or `/mafia`) → everyone taps **Join + DM** → host **Start**.

Lab supergroup: `Qorashahar Lab` (`-1004307184963`). Old basic table `-5042113726` cannot promote bots.

Sticker pack: https://t.me/addstickers/TezMafia_by_menarzullayev

Default timers: discussion 90s, night 45s, vote 45s.

UI: VectorGuard custom emoji (`<tg-emoji>`), tugma `style` + `icon_custom_emoji_id`, ovoz tally, ovozni yechish, DM message effect, reaksiya, `/help` rich message.

```bash
.venv/bin/pytest -q --cov=tezmafia
.venv/bin/python -m tezmafia.qa_gate   # QA-01..QA-100, 100/100 shart
```

JIRA-board QA: `tezmafia/qa_catalog.py` (100 ticket), `tests/test_qa_board.py`, `docs/qa/last-run.json`.
