from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:  # Optional: only required when using Postgres/Neon.
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.exc import IntegrityError as SAIntegrityError
except Exception:  # pragma: no cover
    create_engine = None  # type: ignore[assignment]
    text = None  # type: ignore[assignment]
    Engine = object  # type: ignore[misc,assignment]
    SAIntegrityError = Exception  # type: ignore[misc,assignment]


DEFAULT_SETTINGS: dict[str, str] = {
    "team_columns": "Home",
    "team_rows": "Away",
    "price_per_square": "5",
    "board_locked": "0",
    "row_digits_json": "",
    "col_digits_json": "",
    "max_boxes_per_user": "0",
}

_DB_PATH_CACHE: Path | None = None
_ENGINE_CACHE: Engine | None = None


def _now_ts() -> int:
    return int(time.time())


def db_path() -> Path:
    global _DB_PATH_CACHE
    if _DB_PATH_CACHE is not None:
        return _DB_PATH_CACHE

    env_path = os.getenv("SUPERBOWL_SQUARES_DB_PATH")
    if env_path:
        p = Path(env_path).expanduser()
        if not p.is_absolute():
            p = (Path(__file__).resolve().parent / p)
        try:
            _DB_PATH_CACHE = p.resolve()
        except FileNotFoundError:
            _DB_PATH_CACHE = p.parent.resolve() / p.name
        return _DB_PATH_CACHE

    # Default path for local dev, but this may be read-only on hosted platforms.
    _DB_PATH_CACHE = Path(__file__).resolve().parent / "data" / "squares.db"
    return _DB_PATH_CACHE


def _resolve_writable_db_path() -> Path:
    # If user provided a path, use it (and let mkdir errors surface).
    if os.getenv("SUPERBOWL_SQUARES_DB_PATH"):
        return db_path()

    candidates = [
        Path(__file__).resolve().parent / "data" / "squares.db",
        Path.home() / ".superbowl_squares" / "squares.db",
        Path("/tmp") / "superbowl_squares.db",
    ]
    for p in candidates:
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            return p
        except OSError:
            continue
    return candidates[-1]


def connect() -> sqlite3.Connection:
    global _DB_PATH_CACHE
    path = _resolve_writable_db_path()
    _DB_PATH_CACHE = path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def db() -> Iterator[Any]:
    if database_url():
        engine = _get_engine()
        with engine.begin() as conn:
            yield conn
        return

    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def database_url() -> str | None:
    return (
        os.getenv("DATABASE_URL")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRES_URL_NON_POOLING")
    )


def using_postgres() -> bool:
    return bool(database_url())


def db_backend_label() -> str:
    return "postgres" if using_postgres() else "sqlite"


def _normalize_database_url(url: str) -> str:
    # Neon commonly provides `postgres://...` which SQLAlchemy expects as `postgresql://...`.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]

    parsed = urlparse(url)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    q.setdefault("sslmode", "require")
    return urlunparse(parsed._replace(query=urlencode(q)))


def _get_engine() -> Engine:
    global _ENGINE_CACHE
    if _ENGINE_CACHE is not None:
        return _ENGINE_CACHE
    if not create_engine:
        raise RuntimeError("SQLAlchemy is not installed; add it to requirements.txt to use Postgres.")
    url = database_url()
    if not url:
        raise RuntimeError("No DATABASE_URL configured.")
    _ENGINE_CACHE = create_engine(_normalize_database_url(url), pool_pre_ping=True)
    return _ENGINE_CACHE


def _is_sqlite_conn(conn: Any) -> bool:
    return isinstance(conn, sqlite3.Connection)


def _execute(conn: Any, sql: str, params: dict[str, Any] | None = None) -> Any:
    if _is_sqlite_conn(conn):
        return conn.execute(sql, params or {})
    return conn.execute(text(sql), params or {})


def _fetchone(conn: Any, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    if _is_sqlite_conn(conn):
        row = conn.execute(sql, params or {}).fetchone()
        return dict(row) if row else None
    row = conn.execute(text(sql), params or {}).mappings().fetchone()
    return dict(row) if row else None


def _fetchall(conn: Any, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if _is_sqlite_conn(conn):
        return [dict(r) for r in conn.execute(sql, params or {}).fetchall()]
    return [dict(r) for r in conn.execute(text(sql), params or {}).mappings().fetchall()]


def init_db(conn: Any) -> None:
    if _is_sqlite_conn(conn):
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
    else:
        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS users (
              id BIGSERIAL PRIMARY KEY,
              username TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              salt_b64 TEXT NOT NULL,
              password_hash_b64 TEXT NOT NULL,
              is_admin BOOLEAN NOT NULL DEFAULT FALSE,
              created_at_ts BIGINT NOT NULL
            )
            """,
        )
        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS squares (
              id INTEGER PRIMARY KEY,
              owner_user_id BIGINT NULL REFERENCES users(id),
              updated_at_ts BIGINT NOT NULL
            )
            """,
        )
        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS settings (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at_ts BIGINT NOT NULL
            )
            """,
        )
        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS scores (
              quarter INTEGER PRIMARY KEY,
              rows_score INTEGER NOT NULL,
              cols_score INTEGER NOT NULL,
              updated_at_ts BIGINT NOT NULL,
              updated_by_user_id BIGINT NULL REFERENCES users(id)
            )
            """,
        )
        _execute(
            conn,
            """
            CREATE TABLE IF NOT EXISTS audit_log (
              id BIGSERIAL PRIMARY KEY,
              created_at_ts BIGINT NOT NULL,
              actor_user_id BIGINT NULL REFERENCES users(id),
              action TEXT NOT NULL,
              details_json TEXT NOT NULL
            )
            """,
        )

    # Pre-populate 100 squares if empty
    existing_row = _fetchone(conn, "SELECT COUNT(*) AS c FROM squares")
    existing = int(existing_row["c"]) if existing_row else 0
    if existing == 0:
        now = _now_ts()
        if _is_sqlite_conn(conn):
            conn.executemany(
                "INSERT INTO squares (id, owner_user_id, updated_at_ts) VALUES (:id, NULL, :ts)",
                [{"id": i, "ts": now} for i in range(100)],
            )
        else:
            for i in range(100):
                _execute(
                    conn,
                    """
                    INSERT INTO squares (id, owner_user_id, updated_at_ts)
                    VALUES (:id, NULL, :ts)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {"id": i, "ts": now},
                )

    # Ensure default settings exist
    now = _now_ts()
    for k, v in DEFAULT_SETTINGS.items():
        if _is_sqlite_conn(conn):
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value, updated_at_ts) VALUES (:k, :v, :ts)",
                {"k": k, "v": v, "ts": now},
            )
        else:
            _execute(
                conn,
                """
                INSERT INTO settings (key, value, updated_at_ts)
                VALUES (:k, :v, :ts)
                ON CONFLICT (key) DO NOTHING
                """,
                {"k": k, "v": v, "ts": now},
            )

    # Seed score rows for quarters 1-4
    for q in (1, 2, 3, 4):
        if _is_sqlite_conn(conn):
            conn.execute(
                """
                INSERT OR IGNORE INTO scores (quarter, rows_score, cols_score, updated_at_ts, updated_by_user_id)
                VALUES (:q, 0, 0, :ts, NULL)
                """,
                {"q": q, "ts": now},
            )
        else:
            _execute(
                conn,
                """
                INSERT INTO scores (quarter, rows_score, cols_score, updated_at_ts, updated_by_user_id)
                VALUES (:q, 0, 0, :ts, NULL)
                ON CONFLICT (quarter) DO NOTHING
                """,
                {"q": q, "ts": now},
            )


def get_setting(conn: Any, key: str) -> str:
    row = _fetchone(conn, "SELECT value FROM settings WHERE key = :key", {"key": key})
    if not row:
        return DEFAULT_SETTINGS.get(key, "")
    return str(row["value"])


def set_setting(conn: Any, key: str, value: str) -> None:
    _execute(
        conn,
        """
        INSERT INTO settings (key, value, updated_at_ts)
        VALUES (:key, :value, :ts)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at_ts = excluded.updated_at_ts
        """,
        {"key": key, "value": value, "ts": _now_ts()},
    )


def log_action(conn: Any, actor_user_id: int | None, action: str, details: dict[str, Any]) -> None:
    _execute(
        conn,
        "INSERT INTO audit_log (created_at_ts, actor_user_id, action, details_json) VALUES (:ts, :actor, :action, :details)",
        {
            "ts": _now_ts(),
            "actor": actor_user_id,
            "action": action,
            "details": json.dumps(details, separators=(",", ":")),
        },
    )


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    is_admin: bool


def any_users_exist(conn: Any) -> bool:
    row = _fetchone(conn, "SELECT 1 AS ok FROM users LIMIT 1")
    return bool(row and row.get("ok"))


def get_user_by_username(conn: Any, username: str) -> dict[str, Any] | None:
    return _fetchone(conn, "SELECT * FROM users WHERE username = :username", {"username": username})


def get_user(conn: Any, user_id: int) -> User | None:
    row = _fetchone(conn, "SELECT id, username, display_name, is_admin FROM users WHERE id = :id", {"id": user_id})
    if not row:
        return None
    return User(
        id=int(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        is_admin=bool(row["is_admin"]),
    )


def create_user(
    conn: Any,
    *,
    username: str,
    display_name: str,
    salt_b64: str,
    password_hash_b64: str,
    is_admin: bool,
) -> int:
    params = {
        "username": username.strip().lower(),
        "display_name": display_name.strip(),
        "salt_b64": salt_b64,
        "password_hash_b64": password_hash_b64,
        "is_admin": bool(is_admin),
        "ts": _now_ts(),
    }
    if _is_sqlite_conn(conn):
        cur = conn.execute(
            """
            INSERT INTO users (username, display_name, salt_b64, password_hash_b64, is_admin, created_at_ts)
            VALUES (:username, :display_name, :salt_b64, :password_hash_b64, :is_admin, :ts)
            """,
            {**params, "is_admin": int(bool(is_admin))},
        )
        return int(cur.lastrowid)

    row = _fetchone(
        conn,
        """
        INSERT INTO users (username, display_name, salt_b64, password_hash_b64, is_admin, created_at_ts)
        VALUES (:username, :display_name, :salt_b64, :password_hash_b64, :is_admin, :ts)
        RETURNING id
        """,
        params,
    )
    if not row:
        raise RuntimeError("Failed to create user.")
    return int(row["id"])


def list_squares(conn: Any) -> list[dict[str, Any]]:
    return _fetchall(
        conn,
        """
        SELECT s.id, s.owner_user_id, s.updated_at_ts, u.display_name AS owner_display_name
        FROM squares s
        LEFT JOIN users u ON u.id = s.owner_user_id
        ORDER BY s.id
        """,
    )


def set_square_owner(conn: Any, square_id: int, owner_user_id: int | None) -> None:
    _execute(
        conn,
        "UPDATE squares SET owner_user_id = :owner, updated_at_ts = :ts WHERE id = :id",
        {"owner": owner_user_id, "ts": _now_ts(), "id": square_id},
    )


def get_score(conn: Any, quarter: int) -> dict[str, Any]:
    row = _fetchone(conn, "SELECT * FROM scores WHERE quarter = :q", {"q": quarter})
    if not row:
        raise ValueError(f"Missing score row for quarter {quarter}")
    return row


def set_score(conn: Any, *, quarter: int, rows_score: int, cols_score: int, updated_by_user_id: int) -> None:
    _execute(
        conn,
        """
        UPDATE scores
        SET rows_score = :rows_score, cols_score = :cols_score, updated_at_ts = :ts, updated_by_user_id = :uid
        WHERE quarter = :q
        """,
        {"rows_score": rows_score, "cols_score": cols_score, "ts": _now_ts(), "uid": updated_by_user_id, "q": quarter},
    )


def recent_audit(conn: Any, limit: int = 50) -> list[dict[str, Any]]:
    return _fetchall(
        conn,
        """
        SELECT a.*, u.display_name AS actor_display_name
        FROM audit_log a
        LEFT JOIN users u ON u.id = a.actor_user_id
        ORDER BY a.id DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )


def count_user_squares(conn: Any, user_id: int) -> int:
    row = _fetchone(conn, "SELECT COUNT(*) AS c FROM squares WHERE owner_user_id = :uid", {"uid": user_id})
    return int(row["c"]) if row else 0


def get_square_owner_user_id(conn: Any, square_id: int) -> int | None:
    row = _fetchone(conn, "SELECT owner_user_id FROM squares WHERE id = :id", {"id": square_id})
    if not row:
        return None
    owner = row.get("owner_user_id")
    return int(owner) if owner is not None else None


def list_users_basic(conn: Any) -> list[dict[str, Any]]:
    return _fetchall(conn, "SELECT id, display_name FROM users ORDER BY display_name")


def reset_board_keep_users(conn: Any) -> None:
    now = _now_ts()
    _execute(conn, "UPDATE squares SET owner_user_id = NULL, updated_at_ts = :ts", {"ts": now})
    _execute(
        conn,
        "UPDATE scores SET rows_score = 0, cols_score = 0, updated_at_ts = :ts, updated_by_user_id = NULL",
        {"ts": now},
    )
    set_setting(conn, "row_digits_json", "")
    set_setting(conn, "col_digits_json", "")
    set_setting(conn, "board_locked", "0")


def prune_audit_log(conn: Any, *, keep_last: int) -> None:
    if int(keep_last) <= 0:
        _execute(conn, "DELETE FROM audit_log")
        return
    _execute(
        conn,
        """
        DELETE FROM audit_log
        WHERE id NOT IN (
          SELECT id FROM audit_log ORDER BY id DESC LIMIT :keep
        )
        """,
        {"keep": int(keep_last)},
    )


def vacuum_optimize(conn: Any) -> None:
    if not _is_sqlite_conn(conn):
        return
    conn.commit()
    conn.execute("VACUUM")
    conn.execute("PRAGMA optimize")


def is_username_taken_error(exc: Exception) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return True
    if isinstance(exc, SAIntegrityError):
        orig = getattr(exc, "orig", None)
        if getattr(orig, "pgcode", None) == "23505":
            return True
        msg = (str(orig) or str(exc)).lower()
        return ("unique" in msg or "duplicate" in msg) and "username" in msg
    return False


def ensure_admin_from_env(conn: Any) -> int | None:
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
    _execute(
        conn,
        """
        UPDATE users
        SET is_admin = 1,
            salt_b64 = :salt_b64,
            password_hash_b64 = :password_hash_b64,
            display_name = :display_name
        WHERE id = :id
        """,
        {
            "salt_b64": salt_b64,
            "password_hash_b64": hash_b64,
            "display_name": display_name or str(row["display_name"]),
            "id": user_id,
        },
    )
    log_action(conn, user_id, "bootstrap_admin_update", {"username": username})
    return user_id
