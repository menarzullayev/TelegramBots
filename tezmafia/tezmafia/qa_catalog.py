"""JIRA-board QA catalog: 12 categories, QA-01..QA-100. Source of truth for the gate."""

from __future__ import annotations

TICKETS: list[dict[str, str]] = [
    # 1. Functional
    {"id": "QA-01", "title": "Unit — resolve_votes / start / win_check", "cat": "Functional", "pri": "P0"},
    {"id": "QA-02", "title": "Integration — engine + sqlite Store", "cat": "Functional", "pri": "P0"},
    {"id": "QA-03", "title": "API — Update → handler → response", "cat": "Functional", "pri": "P0"},
    {"id": "QA-04", "title": "E2E — Join → Start → Night → Vote → Winner", "cat": "Functional", "pri": "P0"},
    {"id": "QA-05", "title": "System — production Settings + App + DB", "cat": "Functional", "pri": "P0"},
    {"id": "QA-06", "title": "UAT — 21 rol + shop + /buy qabul matnlari", "cat": "Functional", "pri": "P1"},
    # 2. Regression
    {"id": "QA-07", "title": "Regression — bag + N1 komissar otish yo‘q", "cat": "Regression", "pri": "P1"},
    {"id": "QA-08", "title": "Smoke — import / Settings / Store.init", "cat": "Regression", "pri": "P0"},
    {"id": "QA-09", "title": "Sanity — /buy alias resolve_item", "cat": "Regression", "pri": "P1"},
    {"id": "QA-10", "title": "Snapshot — night_kb N1 faqat tekshir", "cat": "Regression", "pri": "P1"},
    # 3. Performance
    {"id": "QA-11", "title": "Load — parallel vote", "cat": "Performance", "pri": "P1"},
    {"id": "QA-12", "title": "Stress — 500 night_action urinish", "cat": "Performance", "pri": "P1"},
    {"id": "QA-13", "title": "Spike — 0 → ko‘p join → 0", "cat": "Performance", "pri": "P1"},
    {"id": "QA-14", "title": "Endurance — ketma-ket mini-o‘yinlar", "cat": "Performance", "pri": "P2"},
    {"id": "QA-15", "title": "Volume — ko‘p game row sqlite", "cat": "Performance", "pri": "P2"},
    # 4. Concurrency
    {"id": "QA-16", "title": "Race — ikki mafia bir vaqtda target", "cat": "Concurrency", "pri": "P0"},
    {"id": "QA-17", "title": "Concurrent callback — 10 vote birga", "cat": "Concurrency", "pri": "P0"},
    {"id": "QA-18", "title": "Transaction — persist version", "cat": "Concurrency", "pri": "P0"},
    {"id": "QA-19", "title": "Deadlock — Store + App.lock", "cat": "Concurrency", "pri": "P0"},
    {"id": "QA-20", "title": "Idempotency — bir xil vote 5×", "cat": "Concurrency", "pri": "P0"},
    # 5. Telegram
    {"id": "QA-21", "title": "Webhook — polling-only shartnoma", "cat": "Telegram", "pri": "P1"},
    {"id": "QA-22", "title": "Polling — start_polling yo‘li", "cat": "Telegram", "pri": "P1"},
    {"id": "QA-23", "title": "CallbackQuery — inline vote", "cat": "Telegram", "pri": "P0"},
    {"id": "QA-24", "title": "Message Edit — refresh_vote", "cat": "Telegram", "pri": "P1"},
    {"id": "QA-25", "title": "Delete Message — night_delete", "cat": "Telegram", "pri": "P1"},
    {"id": "QA-26", "title": "Deep Link — /start g_", "cat": "Telegram", "pri": "P0"},
    {"id": "QA-27", "title": "Group Permission — mute BadRequest", "cat": "Telegram", "pri": "P1"},
    {"id": "QA-28", "title": "Private Chat — /action faqat DM", "cat": "Telegram", "pri": "P0"},
    {"id": "QA-29", "title": "Inline Keyboard — vote/shop/menu", "cat": "Telegram", "pri": "P0"},
    {"id": "QA-30", "title": "HTML — html_label escape", "cat": "Telegram", "pri": "P1"},
    # 6. Security
    {"id": "QA-31", "title": "Authentication — begona vote yo‘q", "cat": "Security", "pri": "P1"},
    {"id": "QA-32", "title": "Authorization — tinch detective action yo‘q", "cat": "Security", "pri": "P1"},
    {"id": "QA-33", "title": "Input Validation — yomon callback_data", "cat": "Security", "pri": "P1"},
    {"id": "QA-34", "title": "Injection — SQL/HTML ism", "cat": "Security", "pri": "P1"},
    {"id": "QA-35", "title": "Replay — eski vote fazadan keyin", "cat": "Security", "pri": "P1"},
    # 7. Reliability
    {"id": "QA-36", "title": "Recovery — bot restart NIGHT", "cat": "Reliability", "pri": "P1"},
    {"id": "QA-37", "title": "Failover — sqlite re-init (Redis yo‘q)", "cat": "Reliability", "pri": "P1"},
    {"id": "QA-38", "title": "Network Failure — TelegramForbidden", "cat": "Reliability", "pri": "P1"},
    {"id": "QA-39", "title": "Retry — 429 / API xato yutiladi", "cat": "Reliability", "pri": "P1"},
    {"id": "QA-40", "title": "Offline Queue — muddati o‘tgan recover", "cat": "Reliability", "pri": "P1"},
    # 8. State machine
    {"id": "QA-41", "title": "Phase — LOBBY → NIGHT", "cat": "StateMachine", "pri": "P0"},
    {"id": "QA-42", "title": "Invalid transition — DAY → start", "cat": "StateMachine", "pri": "P0"},
    {"id": "QA-43", "title": "Round increment", "cat": "StateMachine", "pri": "P0"},
    {"id": "QA-44", "title": "Win condition — mafia", "cat": "StateMachine", "pri": "P0"},
    {"id": "QA-45", "title": "Draw — vote tie", "cat": "StateMachine", "pri": "P0"},
    # 9. Database
    {"id": "QA-46", "title": "Migration — next_role ALTER", "cat": "Database", "pri": "P1"},
    {"id": "QA-47", "title": "Constraint — stats PK", "cat": "Database", "pri": "P1"},
    {"id": "QA-48", "title": "Rollback — buy no_money", "cat": "Database", "pri": "P1"},
    {"id": "QA-49", "title": "Cascade — cancel finished", "cat": "Database", "pri": "P1"},
    {"id": "QA-50", "title": "Index — unfinished / active_in_chat", "cat": "Database", "pri": "P1"},
    # 10. UX
    {"id": "QA-51", "title": "Message Order — start banner + DM", "cat": "UX", "pri": "P1"},
    {"id": "QA-52", "title": "Timer UX — deadline", "cat": "UX", "pri": "P1"},
    {"id": "QA-53", "title": "Localization — uz/ru/en", "cat": "UX", "pri": "P1"},
    {"id": "QA-54", "title": "Emoji rendering — ce()", "cat": "UX", "pri": "P1"},
    {"id": "QA-55", "title": "Accessibility — tugma matnlari", "cat": "UX", "pri": "P1"},
    # 11. Chaos
    {"id": "QA-56", "title": "Kill cache — Store dispose + qayta ochish", "cat": "Chaos", "pri": "P2"},
    {"id": "QA-57", "title": "Kill DB — init qayta yaratadi", "cat": "Chaos", "pri": "P2"},
    {"id": "QA-58", "title": "Telegram 429 — send yutiladi", "cat": "Chaos", "pri": "P2"},
    {"id": "QA-59", "title": "Random Delay — resolve barqaror", "cat": "Chaos", "pri": "P2"},
    {"id": "QA-60", "title": "Packet Loss — persist/load", "cat": "Chaos", "pri": "P2"},
    # 12. CI/CD
    {"id": "QA-61", "title": "Lint — ast.parse paket", "cat": "CICD", "pri": "P1"},
    {"id": "QA-62", "title": "Format — engine.py tab yo‘q", "cat": "CICD", "pri": "P1"},
    {"id": "QA-63", "title": "Type Check — public engine annotatsiya", "cat": "CICD", "pri": "P1"},
    {"id": "QA-64", "title": "Coverage — 100 ticket to‘liq", "cat": "CICD", "pri": "P0"},
    {"id": "QA-65", "title": "Mutation — bag_for(5).mafia=1 invariant", "cat": "CICD", "pri": "P2"},
    # 66–80 special
    {"id": "QA-66", "title": "Contract — shop ITEMS ↔ Player flags", "cat": "Special", "pri": "P2"},
    {"id": "QA-67", "title": "CDC — ROLE_UZ ↔ ROLE_CARDS", "cat": "Special", "pri": "P2"},
    {"id": "QA-68", "title": "Boundary — bag 4 / 5 / 23", "cat": "Special", "pri": "P1"},
    {"id": "QA-69", "title": "Edge — oxirgi tinch", "cat": "Special", "pri": "P1"},
    {"id": "QA-70", "title": "Negative — o‘lik vote", "cat": "Special", "pri": "P0"},
    {"id": "QA-71", "title": "Positive — tirik vote", "cat": "Special", "pri": "P0"},
    {"id": "QA-72", "title": "Property — seat unique", "cat": "Special", "pri": "P1"},
    {"id": "QA-73", "title": "Fuzz — random callback_data", "cat": "Special", "pri": "P2"},
    {"id": "QA-74", "title": "Randomized — 8 seed start", "cat": "Special", "pri": "P1"},
    {"id": "QA-75", "title": "Deterministic — Random(0)", "cat": "Special", "pri": "P1"},
    {"id": "QA-76", "title": "Serialization — to_dict", "cat": "Special", "pri": "P0"},
    {"id": "QA-77", "title": "Deserialization — from_dict", "cat": "Special", "pri": "P0"},
    {"id": "QA-78", "title": "Clock — night deadline", "cat": "Special", "pri": "P1"},
    {"id": "QA-79", "title": "Timezone — created_at epoch", "cat": "Special", "pri": "P1"},
    {"id": "QA-80", "title": "Scheduler — App.schedule/cancel", "cat": "Special", "pri": "P1"},
    # 81–90 monitoring
    {"id": "QA-81", "title": "Health Check — Store.get_account", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-82", "title": "Readiness — can_start", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-83", "title": "Liveness — recover", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-84", "title": "Metrics — bump_stat coins", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-85", "title": "Logging — recover log", "cat": "Monitoring", "pri": "P2"},
    {"id": "QA-86", "title": "Sentry-proxy — timer exception yutiladi", "cat": "Monitoring", "pri": "P2"},
    {"id": "QA-87", "title": "Alert — game_over matn", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-88", "title": "Tracing — version++", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-89", "title": "Audit — last_death_role", "cat": "Monitoring", "pri": "P1"},
    {"id": "QA-90", "title": "Backup/Restore — sqlite dump", "cat": "Monitoring", "pri": "P2"},
    # 91–100 multiplayer
    {"id": "QA-91", "title": "12 player birga join", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-92", "title": "2 Mafia bir vaqtda target", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-93", "title": "Detective timeout", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-94", "title": "Doctor timeout", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-95", "title": "Vote tie", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-96", "title": "Winner aniqlash", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-97", "title": "Player lobbydan chiqadi", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-98", "title": "Bot restart mid-game", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-99", "title": "Duplicate callback spam", "cat": "Multiplayer", "pri": "P0"},
    {"id": "QA-100", "title": "Ketma-ket o‘yin memory", "cat": "Multiplayer", "pri": "P1"},
]


def ticket_by_n(n: int) -> dict[str, str]:
    return TICKETS[n - 1]


def assert_complete() -> None:
    assert len(TICKETS) == 100
    ids = [t["id"] for t in TICKETS]
    assert ids == [f"QA-{i:02d}" for i in range(1, 101)]
