# TezMafia — GitHub CI/CD

Public repo: [menarzullayev/TelegramBots](https://github.com/menarzullayev/TelegramBots) (`tezmafia/`).

## CI (har PR va `main` push)

Workflow: `.github/workflows/tezmafia-ci.yml`

- `pytest -q`
- `python -m tezmafia.qa_gate` (100/100)

Fake `BOT_TOKEN` va in-memory sqlite — `.env` kerak emas.

## CD (faqat `main`, `tezmafia/**` o‘zgarganda)

Workflow: `.github/workflows/tezmafia-deploy.yml`

SSH orqali hostda `git pull` + `pip install -e ".[dev]"` + `systemctl --user restart tezmafia.service`.

### GitHub Secrets (Settings → Secrets and variables → Actions)

| Secret                 | Ma’nosi                                                                                                                                                     |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `TEZMAFIA_SSH_HOST`    | Deploy server IP yoki hostname                                                                                                                              |
| `TEZMAFIA_SSH_USER`    | SSH user (masalan `nsn`)                                                                                                                                    |
| `TEZMAFIA_SSH_KEY`     | Private key (read-only deploy yoki full user)                                                                                                               |
| `TEZMAFIA_DEPLOY_PATH` | Repo clone yo‘li, masalan `/home/nsn/Workspace/TelegramBots/tezmafia` parent emas — **butun repo** clone bo‘lishi kerak: `/home/nsn/Workspace/TelegramBots` |

### Environment

`tezmafia-production` — ixtiyoriy manual approval (Settings → Environments).

Secrets bo‘lmasa deploy job xato beradi; CI baribir yashil bo‘ladi.

## Windowsda davom ettirish

1. `git clone https://github.com/menarzullayev/TelegramBots.git`
2. Saved Messages’dagi `tezmafia-secrets-backup-*.md` dan `tezmafia/.env` tiklang.
3. `cd tezmafia && python -m venv .venv && .venv\\Scripts\\pip install -e ".[dev]"`
4. GitHub’da secrets qo‘ying, keyin `Actions → TezMafia Deploy → Run workflow` sinab ko‘ring.

## Branch protection (tavsiya)

`main`: required check **TezMafia CI / pytest + QA gate**, 1 approval ixtiyoriy.

Sirlar commit qilinmaydi: root `.gitignore` → `.env`, `*.db`, `tezmafia/data/`.
