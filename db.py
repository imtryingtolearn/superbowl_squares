from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


DEFAULT_SETTINGS: dict[str, str] = {
    "team_columns": "Home",
    "team_rows": "Away",
    "price_per_square": "5",
    "board_locked": "0",
    "row_digits_json": "",
    "col_digits_json": "",
    "max_boxes_per_user": "0",
}


def _now_ts() -> int:
    return int(time.time())


def db_path() -> Path:
    env_path = os.getenv("SUPERBOWL_SQUARES_DB_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent / p)
        try:
            return p.resolve()
        except FileNotFoundError:
            # If the file doesn't exist yet, resolve as much as possible.
            return p.parent.resolve() / p.name
    return Path(__file__).resolve().parent / "data" / "squares.db"


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          display_name TEXT NOT NULL,
          salt_b64 TEXT NOT NULL,
          password_hash_b64 TEXT NOT NULL,
          is_admin INTEGER NOT NULL DEFAULT 0,
          created_at_ts INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS squares (
          id INTEGER PRIMARY KEY,
          owner_user_id INTEGER,
          updated_at_ts INTEGER NOT NULL,
          FOREIGN KEY(owner_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at_ts INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS scores (
          quarter INTEGER PRIMARY KEY,
          rows_score INTEGER NOT NULL,
          cols_score INTEGER NOT NULL,
          updated_at_ts INTEGER NOT NULL,
          updated_by_user_id INTEGER,
          FOREIGN KEY(updated_by_user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at_ts INTEGER NOT NULL,
          actor_user_id INTEGER,
          action TEXT NOT NULL,
          details_json TEXT NOT NULL,
          FOREIGN KEY(actor_user_id) REFERENCES users(id)
        );
        """
    )

    # Pre-populate 100 squares if empty
    existing = conn.execute("SELECT COUNT(*) AS c FROM squares").fetchone()["c"]
    if existing == 0:
        now = _now_ts()
        conn.executemany(
            "INSERT INTO squares (id, owner_user_id, updated_at_ts) VALUES (?, NULL, ?)",
            [(i, now) for i in range(100)],
        )

    # Ensure default settings exist
    now = _now_ts()
    for k, v in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at_ts) VALUES (?, ?, ?)",
            (k, v, now),
        )

    # Seed score rows for quarters 1-4
    for q in (1, 2, 3, 4):
        conn.execute(
            "INSERT OR IGNORE INTO scores (quarter, rows_score, cols_score, updated_at_ts, updated_by_user_id) VALUES (?, 0, 0, ?, NULL)",
            (q, now),
        )


def get_setting(conn: sqlite3.Connection, key: str) -> str:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return DEFAULT_SETTINGS.get(key, "")
    return str(row["value"])


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO settings (key, value, updated_at_ts)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at_ts = excluded.updated_at_ts
        """,
        (key, value, _now_ts()),
    )


def log_action(conn: sqlite3.Connection, actor_user_id: int | None, action: str, details: dict[str, Any]) -> None:
    conn.execute(
        "INSERT INTO audit_log (created_at_ts, actor_user_id, action, details_json) VALUES (?, ?, ?, ?)",
        (_now_ts(), actor_user_id, action, json.dumps(details, separators=(",", ":"))),
    )


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    is_admin: bool


def any_users_exist(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT 1 AS ok FROM users LIMIT 1").fetchone()
    return bool(row)


def get_user_by_username(conn: sqlite3.Connection, username: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute("SELECT id, username, display_name, is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        is_admin=bool(row["is_admin"]),
    )


def create_user(
    conn: sqlite3.Connection,
    *,
    username: str,
    display_name: str,
    salt_b64: str,
    password_hash_b64: str,
    is_admin: bool,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO users (username, display_name, salt_b64, password_hash_b64, is_admin, created_at_ts)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (username.strip().lower(), display_name.strip(), salt_b64, password_hash_b64, int(is_admin), _now_ts()),
    )
    return int(cur.lastrowid)


def list_squares(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT s.id, s.owner_user_id, s.updated_at_ts, u.display_name AS owner_display_name
            FROM squares s
            LEFT JOIN users u ON u.id = s.owner_user_id
            ORDER BY s.id
            """
        ).fetchall()
    )


def set_square_owner(conn: sqlite3.Connection, square_id: int, owner_user_id: int | None) -> None:
    conn.execute(
        "UPDATE squares SET owner_user_id = ?, updated_at_ts = ? WHERE id = ?",
        (owner_user_id, _now_ts(), square_id),
    )


def get_score(conn: sqlite3.Connection, quarter: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM scores WHERE quarter = ?", (quarter,)).fetchone()
    if not row:
        raise ValueError(f"Missing score row for quarter {quarter}")
    return row


def set_score(conn: sqlite3.Connection, *, quarter: int, rows_score: int, cols_score: int, updated_by_user_id: int) -> None:
    conn.execute(
        """
        UPDATE scores
        SET rows_score = ?, cols_score = ?, updated_at_ts = ?, updated_by_user_id = ?
        WHERE quarter = ?
        """,
        (rows_score, cols_score, _now_ts(), updated_by_user_id, quarter),
    )


def recent_audit(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            """
            SELECT a.*, u.display_name AS actor_display_name
            FROM audit_log a
            LEFT JOIN users u ON u.id = a.actor_user_id
            ORDER BY a.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    )


def ensure_admin_from_env(conn: sqlite3.Connection) -> int | None:
    username = (os.getenv("SUPERBOWL_ADMIN_USERNAME") or "").strip().lower()
    password = os.getenv("SUPERBOWL_ADMIN_PASSWORD") or ""
    display_name = (os.getenv("SUPERBOWL_ADMIN_DISPLAY_NAME") or username or "Admin").strip()

    if not username or not password:
        return None

    # Local import to keep layering simple.
    import security  # type: ignore

    row = get_user_by_username(conn, username)
    salt_b64, hash_b64 = security.hash_password(password)
    if not row:
        user_id = create_user(
            conn,
            username=username,
            display_name=display_name or username,
            salt_b64=salt_b64,
            password_hash_b64=hash_b64,
            is_admin=True,
        )
        log_action(conn, user_id, "bootstrap_admin", {"username": username})
        return user_id

    user_id = int(row["id"])
    conn.execute(
        """
        UPDATE users
        SET is_admin = 1,
            salt_b64 = ?,
            password_hash_b64 = ?,
            display_name = ?
        WHERE id = ?
        """,
        (salt_b64, hash_b64, display_name or str(row["display_name"]), user_id),
    )
    log_action(conn, user_id, "bootstrap_admin_update", {"username": username})
    return user_id
