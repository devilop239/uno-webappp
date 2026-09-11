# UNO Arena webapp

The project keeps the original Python/Aiogram Telegram bot and its game engine. The webapp uses the existing FastAPI layer and currently exposes the Classic mode at `/`.

## Run locally or on Replit

```bash
uvicorn app:app --host 0.0.0.0 --port 5000
```

The Replit workflow is configured to run the same command on port 5000.

## Webapp configuration

- A Telegram WebApp user is taken from `Telegram.WebApp.initDataUnsafe.user` when available.
- Visitors outside Telegram are asked for a display name and receive a temporary guest identity.
- MongoDB is optional for the web game. Set `MONGO_URI` when persistent stats are needed.
- `SESSION_SECRET` is used to sign anonymous room sessions when `UNO_SESSION_SECRET` is not set.

The current web release intentionally limits the lobby to Classic UNO. The server remains the source of truth for card legality, stacking, draw penalties, Wild color changes, and bluff capabilities. Additional modes should be added through the mode API and game engine rather than reimplementing rules in the browser.