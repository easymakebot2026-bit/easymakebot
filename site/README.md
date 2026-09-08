# easymakebot marketing site

Two self-contained static pages — no build step, no dependencies. Every asset
(CSS, JS, the logo SVG) is inlined; the only external request is Google Fonts.

| File         | What it is |
|--------------|------------|
| `index.html` | Bilingual (FA/EN) landing + tutorial page. Explains the bot's five build tools, the visual builder, the 4-step "zero to live" flow, and pricing (72h free trial → 490,000 Toman / $10 monthly). |
| `admin.html` | Bilingual platform-admin dashboard mock: overview KPIs, users table, bot management (suspend / grant access / rename / delete), broadcast composer. Demo data only — see below. |
| `assets/`    | `logo-256.png` (the bot logo used in the header, chat mock and favicon) and `logo.png` (the 2000×2000 original). Both pages reference `assets/logo-256.png`; the published Artifact versions inline it as a data URI instead. |

## Serving

Any static host works. Locally:

```bash
python -m http.server 4599 --directory site
```

then open <http://localhost:4599/index.html>.

## Notes

- **Language**: defaults to Persian (RTL). The `فارسی ⇄ EN` toggle flips
  direction and swaps every UI string; the choice is saved in `localStorage`.
- **Theme**: follows the OS by default; the ◐ button forces light/dark.
- **`admin.html` is a design prototype.** The lock screen is cosmetic (demo key
  `1234`) and every action only mutates in-page state — nothing is sent or
  persisted. In the real product this view is the Telegram `/easybotadmin`
  panel, gated to `PLATFORM_ADMIN_ID` (see `bot/handlers/easybotadmin.py` and
  `bot/admin_panel.py`). Wiring it to a real HTTP endpoint would mean serving
  the same queries from `bot/admin_panel.py` as JSON.
