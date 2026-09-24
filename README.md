# WARDROBE — Multi-User Password Edition

WARDROBE is a FastAPI + SQLite wardrobe/styling app with private, user-scoped wardrobe data.

## Authentication

There is no OTP or SMS service. Users create an account with:
- Indian mobile number
- Password (minimum 8 characters)

They then log in with the same mobile number + password. Passwords are stored as PBKDF2-SHA256 hashes, never as plain text.

## Local setup

```bash
python -m venv venv
venv\\Scripts\\activate
python -m pip install -r requirements.txt
```

Create `.env`:

```env
SESSION_SECRET=replace-with-a-long-random-secret
COOKIE_SECURE=false
```

Run:

```bash
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Multi-user isolation

Every clothes, favorites, laundry state, outfit history, Style DNA result, and uploaded image is scoped to the logged-in user's ID.

## Production notes

For a public deployment, use a strong random `SESSION_SECRET`, enable `COOKIE_SECURE=true` behind HTTPS, and use persistent production storage for the database and uploaded images.

## V10 weather update
- Uses browser geolocation only when the user grants permission.
- Fetches current weather from Open-Meteo using the browser coordinates.
- Weather is used by the existing outfit scoring system (`hot`, `warm`, `mild`, `cool`, `rainy`).
- Shows temperature, feels-like temperature, condition, and a location label in the wardrobe stylist.
- If location permission is unavailable, the weather control can be double-clicked to enter a city manually.
- Precise coordinates are kept client-side and are not sent to the WARDROBE backend.
