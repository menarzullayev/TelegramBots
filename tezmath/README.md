# TezMath 🤖📐

Enterprise-grade Telegram bot for solving math problems using AI (Claude Sonnet).

[![CI](https://github.com/menarzullayev/tezmath/actions/workflows/ci.yml/badge.svg)](https://github.com/menarzullayev/tezmath/actions)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

## Features

- **AI-powered math solving** — Claude Sonnet solves any math problem step-by-step with LaTeX notation
- **Photo support** — Send a photo of a math problem, bot reads and solves it via OCR + AI
- **Multilingual** — Uzbek 🇺🇿 and Russian 🇷🇺
- **Freemium model** — 5 free solves/day, unlimited with Premium
- **Payment integration** — Payme, Click, Telegram Stars
- **Rating system** — Rate each solution (1–5 stars)
- **Admin panel** — User management, analytics, broadcast

## Architecture

```
tezmath/
├── services/
│   ├── bot-gateway/      # Telegram bot (python-telegram-bot)
│   ├── ai-solver/        # AI worker (Claude / GPT-4o / Gemini fallback)
│   ├── renderer/         # LaTeX → PNG renderer (FastAPI + matplotlib)
│   ├── payment/          # Payme + Click + Stars (FastAPI)
│   ├── notification/     # Broadcast worker (RabbitMQ consumer)
│   └── admin-panel/      # Admin REST API (FastAPI + JWT)
├── database/
│   └── migrations/       # SQL schema
├── infrastructure/
│   ├── nginx/            # Reverse proxy + SSL
│   └── prometheus/       # Metrics + alerts
└── docker-compose.yml
```

## Quick Start (Dev mode — no Docker needed)

### Requirements
- Python 3.12+
- Telegram Bot Token ([@BotFather](https://t.me/BotFather))
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com))

### Setup

```bash
cd services/bot-gateway

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and fill in BOT_TOKEN and ANTHROPIC_API_KEY

# Run bot (SQLite, no external services needed)
PYTHONPATH=src python src/main.py
```

### Environment Variables

```env
BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
ENVIRONMENT=development
FREE_DAILY_LIMIT=5
ADMIN_IDS=your_telegram_id
SQLITE_PATH=tezmath.db
```

## Full Stack (Docker Compose)

```bash
cp .env.example .env
# Fill in all values in .env

docker compose up -d
```

Services started:
| Service | Port | Description |
|---|---|---|
| bot-gateway | 8000 | Telegram bot |
| renderer | 8001 | LaTeX renderer |
| payment | 8002 | Payment gateway |
| admin-panel | 8003 | Admin API |
| postgres | 5432 | Database |
| redis | 6379 | Rate limiting |
| rabbitmq | 5672 | Message queue |
| minio | 9000 | Image storage |

## Bot Commands

| Command | Description |
|---|---|
| `/start` | Welcome message + main menu |
| `/help` | Usage guide |
| `/profile` | Your stats and remaining daily limit |
| `/premium` | Premium subscription info |
| `/history` | Last 5 solved problems |
| `/settings` | Change language |
| `/admin` | Admin panel (admins only) |

## Tech Stack

- **Bot:** [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) v21
- **AI:** [Anthropic Claude](https://anthropic.com) (claude-sonnet-4-6) with GPT-4o / Gemini fallback
- **Database:** PostgreSQL (production) / SQLite (development)
- **Queue:** RabbitMQ (aio-pika)
- **Cache:** Redis
- **Storage:** MinIO / S3
- **Monitoring:** Prometheus + Grafana + Loki
- **CI/CD:** GitHub Actions

## Development

```bash
# Run tests
make test

# Lint
make lint

# Apply DB migrations
make migrate
```

## Deployment

```bash
# Deploy to staging
make deploy-stage

# Deploy to production (via git tag)
git tag v1.0.0
git push origin v1.0.0
```

## License

MIT © [menarzullayev](https://github.com/menarzullayev)
