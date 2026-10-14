# TezMafia — production (shu PC: Windows + Linux dual boot)

DECISION-15: bot 1000+ foydalanuvchigacha egasining kompyuterida ishlaydi. Server varianti — `DEPLOY-GITHUB.md`.

## Joylashuv

| Narsa | Yo‘l |
| --- | --- |
| Production kodi | `D:\Linux\TelegramBots` — **doim `main`** da (ishlab chiqish boshqa worktree'da) |
| Sozlamalar | `tezmafia\.env` (gitga kirmaydi): `BOT_TOKEN`, `OWNER_ID`, `WEBAPP_URL`, … |
| Baza va loglar | `tezmafia\data\` — Windows va Linux uchun umumiy (D: disk, NTFS) |
| Loglar | `data\logs\bot.log` (5 MB × 5 rotatsiya), `runner.log` (supervisor), `stderr.log` (faqat ogohlantirish va qulash) |

Dev worktree: `git worktree add ../TelegramBots-dev <branch>` — production papkasida branch almashtirilmaydi,
aks holda bot qulab qayta tushsa merge qilinmagan kodni ishga tushiradi.

## Windows

- **Avto-start:** "TezMafia Bot" scheduled task, login'da `pythonw.exe scripts\windows\supervisor.py`.
  O‘rnatish yoki yangilash: `powershell -File tezmafia\scripts\windows\install-autostart.ps1`.
- **Supervisor** botni konsolsiz (`pythonw`) ishga tushiradi va har chiqishdan 10 s keyin qayta tushiradi.
  Faqat 75-kod (boshqa nusxa allaqachon ishlayapti) to‘xtatadi. PowerShell runner Task Scheduler'ning yashirin
  konsolida `STATUS_CONTROL_C_EXIT` bilan o‘lardi — shuning uchun konsol umuman yo‘q.
- **Deploy** (PR merge qilingach):
  ```powershell
  cd D:\Linux\TelegramBots; git pull --ff-only origin main
  Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match '-m tezmafia' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  ```
  Supervisor ~10 s ichida yangi kod bilan qayta tushiradi; egasiga `✅ TezMafia ishga tushdi (<commit>)` keladi.
  `Stop-ScheduledTask` ishlatilmaydi (asinxron, yangi nusxani ham to‘xtatib qo‘yishi mumkin).

## Linux (dual boot)

- Bir marta: `bash tezmafia/scripts/linux/install-autostart.sh` (D: diskdagi repodan). U venv'ni `~/.local/share/tezmafia`
  ga o‘rnatadi va systemd user service `tezmafia` ni yoqadi; kod, `.env` va `data/` — Windows bilan bitta.
- **Shart:** Windows'da Fast Startup o‘chiq bo‘lsin (`powercfg /h off` yoki Boshqaruv paneli → Quvvat → "Tez ishga
  tushirish"). Aks holda Linux D: ni faqat o‘qish uchun ochadi va skript xato beradi.
- D: Linux'da boot paytida avtomatik ulanmagan bo‘lsa, skript `/etc/fstab` uchun namuna qatorni ko‘rsatadi.

## Mini App va tunnel

- Bot ichidagi server: `127.0.0.1:8796` (`WEBAPP_PORT`). Ommaviy manzil: `https://mafia.bugvector.uz/` (`WEBAPP_URL`).
- Cloudflare tunnel `baed7e7f-…` (`C:\Users\nsn\.cloudflared\config.yml`) qoidasi:
  `mafia.bugvector.uz → http://127.0.0.1:8796`. DNS: `cloudflared tunnel route dns <tunnel> mafia.bugvector.uz`.
- cloudflared restarti tunneldagi **barcha** saytlarni (rankwant.uz va boshqalar) bir necha soniyaga uzadi:
  restartdan oldin va keyin saytlar holatini solishtirish kerak. Qayta ishga tushirish — `autostart-tunnel.ps1`.

## Kuzatuv

- Egasiga DM: ishga tushish, xatolar, qotib qolgan o‘yin (watchdog qayta yoqadi), har to‘lov, kunlik hisobot (`REPORT_HOUR`).
- `/refund <charge_id>` — faqat egasi uchun.
