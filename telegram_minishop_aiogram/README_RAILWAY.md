# Deploy to Railway (Quick Guide)

1) Create New Project → **Deploy from Zip** and upload this archive.
2) In **Variables**, add:
   - `BOT_TOKEN` — token from @BotFather
   - `ADMIN_CHAT_ID` — your Telegram numeric ID
   - `DATABASE_PATH` — `data.sqlite`
3) Start command is already set in `Procfile`: `web: python bot.py`
4) (Optional) Enable a persistent volume for SQLite so orders survive restarts.

Check logs: **Deployments → View Logs**.
