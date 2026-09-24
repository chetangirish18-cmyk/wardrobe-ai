# WARDROBE — final production update

WARDROBE is a FastAPI + vanilla JavaScript AI wardrobe app with mobile-number/password authentication, user-scoped wardrobe data, weather-aware outfit recommendations, favorites, laundry tracking, outfit history, Style DNA, backup/restore, and optional Telegram integration.

## Database

- Local development: SQLite (`wardrobe.db`) when `DATABASE_URL` is empty.
- Production: PostgreSQL when `DATABASE_URL` is set.
- This avoids losing accounts/wardrobes when a Render web service redeploys or restarts.

## Local run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

## Render

1. Create a Render Postgres database.
2. Connect the database to the WARDROBE web service so `DATABASE_URL` is available, or copy the database's Internal Database URL into the web service environment.
3. Keep `SESSION_SECRET` as the same long random secret across deploys.
4. Set `COOKIE_SECURE=true`.
5. Build command: `pip install -r requirements.txt`
6. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
7. Open `/health` after deployment. It should report `{"ok":true,"database":"postgres"}`.

## Uploads

Uploaded clothing images are still filesystem files. On Render Free, local files are ephemeral. If persistent image storage is needed, set `UPLOAD_DIR` to a directory on a paid Render persistent disk (for example `/var/data/uploads`) or move uploads to object storage later.

## Notes

- Passwords are stored as PBKDF2-SHA256 hashes.
- Wardrobe, favorites, laundry, wear history, outfit history, and recommendations are scoped to the logged-in user.
- The browser daily-outfit cache now uses the user's local calendar date instead of UTC.
