# Super Bowl Squares (friends & family)

A simple Streamlit app for running a classic 10x10 Super Bowl squares board:

- People create accounts and claim squares.
- Admin assigns row/column digits (randomized) when ready.
- Admin updates quarter-end scores; the app computes winners.
- An audit log tracks claims, reassignments, and score updates.

## Run locally

From the repo root:

```bash
cd superbowl_squares
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # set admin username/password here
streamlit run app.py
```

The SQLite DB lives at `superbowl_squares/data/squares.db` by default.
On Streamlit Community Cloud (and other hosted setups), the repo directory may be read-only; the app will automatically fall back to a writable location (home directory or `/tmp`). You can also set `SUPERBOWL_SQUARES_DB_PATH` in Streamlit Secrets.

## Neon / Postgres (recommended for Streamlit Cloud)

Streamlit Community Cloud file storage can be wiped/recreated on redeploys, so for a game you care about, use a hosted DB.

1. In Neon: create a project + database and copy the connection string.
2. In Streamlit Cloud → your app → **Settings → Secrets**, add:
   - `DATABASE_URL="postgresql://..."`
   - `SUPERBOWL_ADMIN_USERNAME="tejas"`
   - `SUPERBOWL_ADMIN_PASSWORD="..."`
   - (optional) `SUPERBOWL_ADMIN_DISPLAY_NAME="Tejas"`

Notes:
- Include `sslmode=require` in the URL if Neon provides it (the app will also default it on).
- Admin → Database tools will disable SQLite-only actions when using Postgres.

## Admin setup

Recommended: set `SUPERBOWL_ADMIN_USERNAME` + `SUPERBOWL_ADMIN_PASSWORD` in `superbowl_squares/.env` so the app bootstraps (or updates) the admin user on startup.

If you do not set an admin via env vars, the very first account created becomes the admin automatically.

Admin can:
- Set team names and square price
- Assign (or clear) random digits
- Lock/unlock the board
- Reassign squares
- Reset the board for reuse

## How to run the game (simple flow)

1. Share the app link with friends/family so they can create accounts and claim squares.
2. When you are ready (often once most squares are claimed): Admin → **Assign random digits**.
3. Optionally: Admin → **Lock board** (prevents last-minute changes).
4. At the end of each quarter: Scores → Admin updates the quarter score.
5. Winners appear automatically in Home and Scores.

## Interface style tips (casual + easy)

- Keep labels human: use "Claim squares" / "My squares" / "Scores" instead of admin-y terms.
- Show state at a glance: the Home page uses metrics (claimed count, price, locked/unlocked).
- Prefer simple forms: one action per button (claim, release, assign digits, update score).
- Make changes transparent: the Recent activity log helps avoid arguments.

## Deploy on Streamlit Community Cloud

1. Push this repo to GitHub.
2. In Streamlit Cloud: **New app** → pick the repo.
3. Set the main file path to `superbowl_squares/app.py`.
4. (Optional) Configure a persistent DB:
   - Streamlit Community Cloud may not reliably persist local files across redeploys.
   - For game-night use, default SQLite is usually fine.
   - For longer-term persistence, point `SUPERBOWL_SQUARES_DB_PATH` to a mounted/persistent path (if available) or switch `db.py` to an external hosted database.

## Notes / best practices used here

- Minimal dependencies (Streamlit + pandas).
- Passwords are stored as PBKDF2 hashes (no plaintext).
- SQLite for simple deployment; audit log for transparency.
