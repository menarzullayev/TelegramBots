# TezMafia channel launch series

Source of truth for the channel posts (DECISION-18). Each post is one JSON file in `posts/`;
`scripts/channel_publish.py` turns it into a Telegram rich message (Bot API 10.x blocks) and sends
it to a channel (the private drafts channel first, the public channel after the owner approves).

## Post file schema (`posts/NN-slug.json`)

```json
{
  "id": 1,
  "slug": "what-is-tezmafia",
  "series": "A",
  "segment": "player",
  "hashtags": ["#tanishuv"],
  "visual": {"type": "image", "images": ["banner.jpg"]},
  "uz": {"title": "…", "blocks": [{"p": "…"}, {"list": ["…", "…"]}]},
  "ru": {"title": "…", "blocks": [{"p": "…"}]},
  "en": {"title": "…", "blocks": [{"p": "…"}]},
  "buttons": [{"uz": "Guruhga qo‘shish", "url": "https://t.me/qorashahar_mafia_bot?startgroup=true"}],
  "poll": null
}
```

- `visual.type`: `image` (1 file), `slideshow` (2–8 files), `mock` (a branded chat mock-up rendered by
  `scripts/channel_mock.py` from `visual.mock`), or `none`. Image paths are relative to `assets/raven/`.
- `visual.mock`: `{"chat": "group"|"bot", "messages": [{"from": "user"|"bot", "name": "Aziz", "text": "…",
  "buttons": [["Men o‘ynayman"], ["O‘yinni boshlash · 3/5"]]}]}` — short, realistic, no real personal data.
- Blocks: `{"p": text}`, `{"h": subheading}`, `{"list": [items]}`, `{"quote": text}`, `{"table": [[header…], [row…]]}`.
  Inline markup inside text: `**bold**`, `_italic_`, `[label](https://url)`, `` `/command` ``.
- `buttons`: at most 3; URLs only from: `https://t.me/qorashahar_mafia_bot?startgroup=true`,
  `https://t.me/qorashahar_mafia_bot` (optionally `?start=<payload>`), `https://mafia.bugvector.uz`.
- `poll` (optional, sent right after the post as a native poll): `{"type": "quiz"|"regular", "question": {uz, ru, en},
  "options": [{uz, ru, en}…], "correct": [indexes], "explanation": {uz, ru, en}}`.

## Writing rules

- Uzbek (Latin) is the main text; Russian and English are faithful, slightly shorter versions shown in
  collapsed sections. Use the apostrophe forms of `locales/uz.json` (o‘, g‘, ‘).
- Voice: noir Qorashahar narrator — warm, a little mysterious, playful, second person, never pushy.
- Length: Uzbek 80–300 words. One idea per post. End with a clear next step (command or button).
- Only verified facts (see `inventory.md`). Commands and button labels exactly as in the bot.
- Money: gems, skins, badges and the season pass are cosmetic; coins also buy in-game items
  (shield, mask, gun, role ticket…) and are earned by playing — never claim "no pay-to-win".
- Never post: owner-only commands (`/weekly`, `/refund`), production numbers (users, games),
  synthetic data, infrastructure details, unverified claims. Load test wording: "tested on
  1,000,000 synthetic users and games", never "serves 1M users".
- Season pass starts with the November 2026 season.
