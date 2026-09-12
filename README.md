# UNO Bot

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](./LICENSE)

A feature-rich **UNO** bot for Telegram groups. Players use **inline mode** to play cards from their hand without leaving the chat. Built on **Aiogram 3**, with persistent stats, multiple game modes, and swappable card art.

**Maintainer:** [demon](https://t.me/demon12809) ([@demon12809](https://t.me/demon12809))

---

## Features

### Gameplay

- **Inline play** — type `@YourBot` + space in a group to open your hand and play cards.
- **Game modes** — Classic, Fast, Wild, Rainbow, Text, Team UNO, Sudden Death.
- **Lobby settings** (host, before `/start`):
  - **Hand size** — 7 / 14 / 21 cards
  - **Draw stack** — stack +4 / +8 chains (with bluff challenge)
  - **Deck style** — visual sticker pack only (same rules for all styles)
- **Private battles** — 1v1 matches via DM (`/privatenew`, join codes).
- **Team mode** — shared hands, manual or random teams (`/teamnew`).
- **Rematch** — settings carry over when starting a new lobby after a match.

### Deck styles (visual only)

| Style   | Description                          |
|---------|--------------------------------------|
| Normal  | Default colorblind-friendly stickers |
| Anime   | Anime character card art             |
| Pokemon | Pokémon-themed card art              |

Gameplay, deck composition, and probabilities are **identical** across styles. Rainbow mode currently uses **Normal** art only (alt packs do not include rainbow-only cards yet).

Sticker resolution: `deck_styles.py` → `anime_assets.py` / `pokemon_assets.py` (with automatic fallback to Normal if a sticker is missing).

### Stats & leaderboards

Requires MongoDB (see below). Without it, the bot still runs; stats are skipped.

| Command       | Description              |
|---------------|--------------------------|
| `/mystats`    | Personal dashboard       |
| `/points`     | Total points             |
| `/history`    | Recent matches           |
| `/leaderboard`| Global leaderboard       |
| `/weeklylb`   | Weekly leaderboard       |
| `/monthlylb`  | Monthly leaderboard      |
| `/seasonlb`   | Season leaderboard       |

Private menus: `/help`, `/modes`, `/stats`, `/rules_map`, and related callbacks.

### Group commands (highlights)

| Command        | Description                    |
|----------------|--------------------------------|
| `/new`         | Create a lobby                 |
| `/join`        | Join the lobby                 |
| `/start`       | Start the match                |
| `/status`      | Live game snapshot             |
| `/settings`    | Lobby settings (inline buttons)|
| `/handsize`    | Set starting hand size         |
| `/rules_map`   | Rules for all modes            |

Full command list is registered on startup in `main.py` and listed in `commandlist.txt`.

### Sudo / owner tools (private chat)

Not shown in the public BotFather menu. Requires **sudo** or **owner** access (`BOT_OWNER_IDS` / `add_sudo`).

**Broadcast** (reply to a message, or pass text after the command):

| Copy | Forward |
|------|---------|
| `/broadcast_all` | `/broadcast_all_forward` |
| `/broadcast_users` | `/broadcast_users_forward` |
| `/broadcast_chats` | `/broadcast_chats_forward` |

Aliases: `/broadcast`, `/broadcast_user`, `/broadcast_chat`.

**Other admin:**

- `/link <chat_id>` — export group invite link (bot must be admin with *invite users via link*)
- `/stats`, `/gift_points`, `/ban_user`, `/restart` — see `handlers/admin.py`
- `/add_sudo`, `/remove_sudo`, `/all_sudo` — owner only

---

## Requirements

- **Python 3.11+** (recommended; Docker image uses 3.11)
- **[Aiogram](https://docs.aiogram.dev/) 3.x**
- **[MongoDB](https://www.mongodb.com/)** (optional but recommended for stats, points, match history)
- **gettext** — to compile locale `.po` → `.mo` files (included in Docker build)

---

## Quick start

### 1. Clone and install

```bash
git clone <your-repo-url>
cd <repo-folder>
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

| Variable        | Required | Description                          |
|-----------------|----------|--------------------------------------|
| `TOKEN`         | Yes      | Bot token from [@BotFather](https://t.me/BotFather) |
| `MONGO_URI`     | No       | MongoDB connection string            |
| `MONGO_DB_NAME` | No       | Database name (default: `uno_bot`)     |
| `LOG_GROUP_ID`  | No       | Ops/audit log supergroup             |
| `BOT_OWNER_IDS` | No       | Comma-separated owner user IDs       |

You can also use `config.json` for `token`, `mongo_uri`, and other keys (see `config.py`).

### 3. Compile translations (optional)

```bash
cd locales && ./compile.sh && cd ..
```

If skipped, English strings are used.

### 4. BotFather setup

1. Enable **Inline mode**: `/setinline` → choose your bot → enable.
2. Optional: `/setinlinefeedback` for inline feedback.
3. Commands are set automatically on startup; `commandlist.txt` is a reference copy.

### 5. Run

```bash
python bot.py
```

(`bot.py` delegates to `main.py` — same entry point for Docker and legacy deploy scripts.)

**Important:** Run only **one** poller per `TOKEN` (no second process and no active webhook on the same bot).

---

## MongoDB

1. Create a cluster ([MongoDB Atlas](https://www.mongodb.com/cloud/atlas) or self-hosted).
2. Set `MONGO_URI` in `.env`.
3. On first connection, the bot creates indexes on `player_stats`, `matches`, `point_ledger`, and related collections.

Collections include: `users`, `player_stats`, `matches`, `point_ledger`, `group_bot_first_seen`, `bot_config`, and others used by services under `services/`.

Point and season tuning defaults live in `config.py` (`DEFAULT_WIN_POINTS`, `DEFAULT_STATS_SEASON_ID`, etc.) and can be overridden via `.env`.

---

## Project layout

```
├── main.py              # Aiogram entry (polling)
├── bot.py               # Legacy launcher → main.py
├── config.py            # Environment & tuning
├── game.py              # Game state & lobby settings
├── deck.py              # Card deck logic (shared across styles)
├── card.py              # Card model & default stickers
├── deck_styles.py       # Deck style resolver (normal / anime / pokemon)
├── anime_assets.py      # Anime sticker file IDs
├── pokemon_assets.py    # Pokémon sticker file IDs
├── actions.py           # Play / draw / skip / bluff
├── handlers/            # Commands & callbacks
│   ├── game.py          # Lobby, settings, match flow
│   ├── inline.py        # Inline query gameplay
│   ├── broadcast.py     # Sudo broadcasts
│   ├── link.py          # Sudo invite-link helper
│   └── admin.py         # Owner/sudo admin commands
├── services/            # Stats, matches, private battles, ACL
├── db/                  # MongoDB client
├── locales/             # gettext translations
└── images/              # Card art sources & mode assets
    ├── classic_colorblind/
    └── anime_deck/
```

---

## Docker

```bash
docker build -t uno-bot .
docker run --env-file .env uno-bot
```

Or use `docker-compose.yml` if configured for your deployment.

The image compiles locales during build and runs as user `nobody`.

---

## Deployment Modes (Docker / Render)

This repository can be deployed either as a **Standalone Web Application** or as a **Telegram Bot** using the same Docker image. The mode is selected via the `RUN_MODE` environment variable:

- **`RUN_MODE=webapp`** *(Default)*: Launches the FastAPI web application engine via `uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000}`.
  - **Render Web Service**: Set `RUN_MODE=webapp` in your Render Web Service environment settings. Render automatically injects the `$PORT` environment variable.
- **`RUN_MODE=bot`**: Launches the Telegram bot poller via `python bot.py`.
  - **Render Background Worker**: Set `RUN_MODE=bot` when deploying as a background worker.

---

## Adding a new deck style

1. Add sticker `file_id` maps in a new module (e.g. `neon_assets.py`) with `normal` and `not_playable` dicts (same keys as `str(card)`, e.g. `r_5`, `draw_four`).
2. Register the pack in `STICKER_PACKS` inside `deck_styles.py`.
3. Add a lobby button in `handlers/game.py` (`_deckstyle_keyboard` / `_deckstyle_text`).
4. Place PNG sources under `images/<your_deck>/` if you maintain local art.

Game logic in `deck.py` should **not** be duplicated.

---

## Development

- **Tests:** `pytest` in `test/` (game logic, actions, game manager).
- **Lint / run:** ensure `TOKEN` is set; Mongo optional for local play.
- **Do not commit** `.env`, tokens, or generated secrets.

Upstream credits and translators: [NOTICE](./NOTICE), [TRANSLATORS.md](./TRANSLATORS.md), [AUTHORS.md](./AUTHORS.md).

---

## License

This project is licensed under the **GNU Affero General Public License v3.0** (or later). See [LICENSE](./LICENSE).

Using the bot in production with users over a network requires providing source code to users per AGPL terms. See the license file for full details.
