from __future__ import annotations

import json
import os
import random
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None  # type: ignore

import db
import game_logic
import security

_GLOBAL_CSS = """
<style>
/* Slight rounding for Streamlit containers to make the UI feel softer. */
div[data-testid="stElementContainer"] {
  border-radius: 0.85rem;
}
</style>
"""

_GRID_CSS = """
<style>
__SCOPE__ { width: 100%; }
__SCOPE__ { --sb-cell: clamp(2.25rem, 4.8vw, 3.1rem); --sb-gap: 0.18rem; }
__SCOPE__ [data-testid="stHorizontalBlock"] { gap: 0.18rem !important; }
__SCOPE__ [data-testid="column"] { padding: 0 !important; }
__SCOPE__ div[data-testid="stButton"] { margin: 0 !important; }
__SCOPE__ [data-testid="stElementContainer"] { width: 100% !important; max-width: 100% !important; }

__SCOPE__ .sb-grid-scroll {
  width: 100%;
  overflow-x: auto;
  overflow-y: hidden;
  -webkit-overflow-scrolling: touch;
  padding-bottom: 0.35rem;
}
__SCOPE__ .sb-grid-inner { width: max-content; }
__SCOPE__ .sb-grid-inner [data-testid="stHorizontalBlock"] { width: max-content !important; flex-wrap: nowrap !important; }
__SCOPE__ .sb-grid-inner [data-testid="column"] { min-width: var(--sb-cell) !important; }

__SCOPE__ .team-top {
  font-weight: 900;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  font-size: clamp(1.6rem, 5vw, 2.8rem);
  line-height: 1;
  text-align: center;
  color: #0B0F19;
  margin: 0.2rem 0 0.25rem 0;
}
__SCOPE__ .team-side-wrap {
  width: 100%;
  min-height: calc(var(--sb-cell) * 11 + var(--sb-gap) * 10);
  display: flex;
  align-items: center;
  justify-content: center;
}
__SCOPE__ .team-side {
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: clamp(1.4rem, 5vw, 2.6rem);
  line-height: 1;
  transform: rotate(-90deg);
  color: #0B0F19;
  white-space: nowrap;
}
__SCOPE__ .team-side-mobile {
  display: none;
  font-weight: 900;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  font-size: clamp(1.0rem, 4.5vw, 1.5rem);
  line-height: 1.1;
  text-align: center;
  color: #0B0F19;
  margin: 0.1rem 0 0.45rem 0;
}

__SCOPE__ .digit {
  height: var(--sb-cell);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.6rem;
  font-weight: 900;
  font-size: clamp(1.0rem, 2.4vw, 1.25rem);
  color: #FFFFFF;
  box-shadow: 0 1px 0 rgba(0,0,0,0.06);
}
__SCOPE__ .digit-top {
  background: #E11D48;
  border: 2px solid #F59E0B;
}
__SCOPE__ .digit-left {
  background: #0F4C5C;
}
__SCOPE__ .corner {
  height: var(--sb-cell);
}

__SCOPE__ button {
  width: 100%;
  height: var(--sb-cell);
  padding: 0 !important;
  border-radius: 0.6rem !important;
}

/* Base button variants (Streamlit 1.53 uses data-testid="baseButton-*") */
__SCOPE__ button[data-testid^="baseButton-"] {
  border: 2px solid #64748B !important;
  background: #FFFFFF !important;
  color: #111827 !important;
  box-shadow: 0 1px 0 rgba(0,0,0,0.06);
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  text-align: center !important;
  font-weight: 900 !important;
  font-size: clamp(0.9rem, 2.2vw, 1.1rem) !important;
  line-height: 1 !important;
}
__SCOPE__ button[data-testid^="baseButton-"]:hover:not(:disabled) {
  border-color: #2563EB !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

/* Open squares (tertiary) */
__SCOPE__ button[data-testid="baseButton-tertiary"] {
  background: #FFFFFF !important;
}

/* Make the empty/open marker look centered and subtle */
__SCOPE__ button[data-testid="baseButton-tertiary"] {
  color: #334155 !important;
  font-size: clamp(1.35rem, 4.2vw, 1.7rem) !important;
}

/* Yours (primary) */
__SCOPE__ button[data-testid="baseButton-primary"] {
  background: #FFEDD5 !important;
  border-color: #FB923C !important;
  color: #7C2D12 !important;
}
__SCOPE__ button[data-testid="baseButton-primary"]:hover:not(:disabled) {
  border-color: #F97316 !important;
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.16);
}

/* Will release (secondary) */
__SCOPE__ button[data-testid="baseButton-secondary"]:not(:disabled) {
  background: #FEE2E2 !important;
  border-color: #EF4444 !important;
  color: #7F1D1D !important;
}
__SCOPE__ button[data-testid="baseButton-secondary"]:not(:disabled):hover {
  border-color: #DC2626 !important;
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.16);
}

__SCOPE__ button:disabled {
  opacity: 1;
  background: #F3F4F6;
  color: #6B7280;
}

@media (max-width: 640px) {
  __SCOPE__ { --sb-cell: clamp(2.25rem, 10vw, 2.75rem); --sb-gap: 0.16rem; }
  __SCOPE__ [data-testid="stHorizontalBlock"] { gap: 0.16rem !important; }
  __SCOPE__ .team-top { font-size: clamp(1.25rem, 7vw, 2.0rem); }
  __SCOPE__ .team-side-wrap { display: none; }
  __SCOPE__ .team-side-mobile { display: block; }
  __SCOPE__ button { border-radius: 0.5rem !important; }
  __SCOPE__ .digit { border-radius: 0.5rem; }
  __SCOPE__ .sb-grid-scroll { padding-bottom: 0.25rem; }
}
</style>
"""


def _ts_to_str(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")


def _short_name(name: str) -> str:
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[-1][:1]).upper()

def _cell_label(name: str) -> str:
    first = (name or "").strip().split(" ")[0] if name else ""
    if not first:
        return "☐"
    return first[:6]


def require_login() -> db.User:
    user_id = st.session_state.get("user_id")
    if not user_id:
        st.info("Sign in to claim squares and see your boxes.")
        st.stop()
    with db.db() as conn:
        user = db.get_user(conn, int(user_id))
    if not user:
        st.session_state.pop("user_id", None)
        st.warning("Session expired. Please sign in again.")
        st.stop()
    return user


def require_admin(user: db.User) -> None:
    if not user.is_admin:
        st.error("Admin-only area.")
        st.stop()


def board_df(squares: list[dict]) -> pd.DataFrame:
    cells: list[list[str]] = [["" for _ in range(10)] for _ in range(10)]
    for sq in squares:
        r, c = game_logic.row_col_from_id(int(sq["id"]))
        owner = sq.get("owner_display_name") or ""
        cells[r][c] = _short_name(owner) if owner else ""
    return pd.DataFrame(cells, index=[f"R{r}" for r in range(10)], columns=[f"C{c}" for c in range(10)])

def render_board_grid(
    *,
    squares: list[dict],
    row_digits: list[int] | None,
    col_digits: list[int] | None,
    team_rows: str,
    team_columns: str,
    grid_key_prefix: str,
    click_to_claim: bool,
    on_claim,
    selected_ids: set[int] | None = None,
    on_toggle_select=None,
    allow_toggle_own: bool = True,
    highlight_user_id: int | None = None,
) -> None:
    scope_id = f"sb-grid-{grid_key_prefix}"
    scope_selector = f"div[data-testid='stVerticalBlock']:has(#{scope_id})"
    container = st.container()

    square_map = {int(s["id"]): s for s in squares}
    row_labels = row_digits if row_digits else ["?"] * 10
    col_labels = col_digits if col_digits else ["?"] * 10
    selected_ids = selected_ids or set()

    container.markdown(f"<div id='{scope_id}'></div>", unsafe_allow_html=True)
    container.markdown(_GRID_CSS.replace("__SCOPE__", scope_selector), unsafe_allow_html=True)

    # Layout like the reference image:
    # - team_columns as a big title centered above
    # - team_rows as a big vertical title on the left
    container.markdown(f"<div class='team-top'>{team_columns}</div>", unsafe_allow_html=True)
    container.markdown(f"<div class='team-side-mobile'>{team_rows}</div>", unsafe_allow_html=True)

    outer = container.columns([0.7, 11.3])
    outer[0].markdown(
        f"<div class='team-side-wrap'><div class='team-side'>{team_rows}</div></div>",
        unsafe_allow_html=True,
    )

    grid = outer[1]
    grid.markdown("<div class='sb-grid-scroll'><div class='sb-grid-inner'>", unsafe_allow_html=True)
    header = grid.columns([0.72] + [1] * 10)
    header[0].markdown("<div class='corner'></div>", unsafe_allow_html=True)
    for c in range(10):
        header[c + 1].markdown(f"<div class='digit digit-top'>{col_labels[c]}</div>", unsafe_allow_html=True)

    def _button(container, *, label_: str, key_: str, disabled_: bool, type_: str, help_: str):
        try:
            return container.button(label_, key=key_, disabled=disabled_, type=type_, help=help_)
        except Exception:
            if type_ == "tertiary":
                return container.button(label_, key=key_, disabled=disabled_, type="secondary", help=help_)
            raise

    for r in range(10):
        row_cols = grid.columns([0.72] + [1] * 10)
        row_cols[0].markdown(f"<div class='digit digit-left'>{row_labels[r]}</div>", unsafe_allow_html=True)
        for c in range(10):
            sq_id = game_logic.square_id(r, c)
            sq = square_map[sq_id]
            owner_id = sq.get("owner_user_id")
            owner_name = sq.get("owner_display_name") or ""
            is_selected = int(sq_id) in selected_ids

            can_toggle_open = bool(on_toggle_select) and (not owner_id)
            can_toggle_own = (
                bool(on_toggle_select)
                and allow_toggle_own
                and bool(highlight_user_id)
                and bool(owner_id)
                and int(owner_id) == int(highlight_user_id)
            )
            can_toggle = can_toggle_open or can_toggle_own

            if owner_id:
                label = _cell_label(owner_name)
                if is_selected and can_toggle_own:
                    help_txt = "Will release"
                    button_type = "secondary"
                elif can_toggle_own:
                    help_txt = "Yours"
                    button_type = "primary"
                else:
                    help_txt = owner_name
                    button_type = "secondary"
            else:
                label = "✓" if (is_selected and can_toggle_open and not click_to_claim) else "☐"
                if click_to_claim:
                    help_txt = "Click to claim"
                elif can_toggle_open:
                    help_txt = "Will claim" if is_selected else "Select to claim"
                else:
                    help_txt = "Open"
                button_type = "tertiary"

            disabled = (bool(owner_id) and not can_toggle) or (not click_to_claim and not can_toggle)
            clicked = _button(
                row_cols[c + 1],
                label_=label,
                key_=f"{grid_key_prefix}_{sq_id}",
                disabled_=disabled,
                type_=button_type,
                help_=help_txt,
            )
            if clicked and click_to_claim:
                on_claim(int(sq_id))
            if clicked and (not click_to_claim) and on_toggle_select and can_toggle:
                on_toggle_select(int(sq_id))
    grid.markdown("</div></div>", unsafe_allow_html=True)


def load_state():
    with db.db() as conn:
        db.init_db(conn)
        settings = {
            "team_columns": db.get_setting(conn, "team_columns"),
            "team_rows": db.get_setting(conn, "team_rows"),
            "price_per_square": db.get_setting(conn, "price_per_square"),
            "board_locked": db.get_setting(conn, "board_locked") == "1",
            "row_digits_json": db.get_setting(conn, "row_digits_json"),
            "col_digits_json": db.get_setting(conn, "col_digits_json"),
            "max_boxes_per_user": db.get_setting(conn, "max_boxes_per_user"),
        }
        squares_rows = db.list_squares(conn)
    squares = [dict(r) for r in squares_rows]
    row_digits = game_logic.parse_digits(settings["row_digits_json"])
    col_digits = game_logic.parse_digits(settings["col_digits_json"])
    return settings, squares, row_digits, col_digits


def page_auth():
    st.header("Welcome")
    st.write(
        "This is a simple Super Bowl squares board for friends and family. "
        "Make an account, claim your squares, and check back during the game for quarter winners."
    )

    with db.db() as conn:
        db.init_db(conn)
        has_users = db.any_users_exist(conn)

    tab1, tab2 = st.tabs(["Sign in", "Create account" if has_users else "Create admin account"])

    with tab1:
        with st.form("login"):
            username = st.text_input("Username", placeholder="username", key="login_username")
            password = st.text_input("Password", type="password", key="login_password")
            submitted = st.form_submit_button("Sign in")
        if submitted:
            with db.db() as conn:
                row = db.get_user_by_username(conn, username.strip().lower())
                if not row:
                    st.error("No such user.")
                    st.stop()
                if not security.verify_password(
                    password,
                    salt_b64=str(row["salt_b64"]),
                    password_hash_b64=str(row["password_hash_b64"]),
                ):
                    st.error("Wrong password.")
                    st.stop()
                st.session_state["user_id"] = int(row["id"])
                st.session_state["nav_page"] = "Home"
                db.log_action(conn, int(row["id"]), "login", {})
            st.success("Signed in.")
            st.rerun()

    with tab2:
        st.caption("Keep it simple: pick a username your friends will recognize.")
        with st.form("register"):
            username = st.text_input("Username", placeholder="username", key="register_username")
            display_name = st.text_input("Display name", placeholder="User", key="register_display_name")
            password = st.text_input("Password", type="password", key="register_password")
            password2 = st.text_input("Confirm password", type="password", key="register_password2")
            submitted = st.form_submit_button("Create account")
        if submitted:
            if not username.strip():
                st.error("Username required.")
                st.stop()
            if not display_name.strip():
                st.error("Display name required.")
                st.stop()
            if len(password) < 6:
                st.error("Password must be at least 6 characters.")
                st.stop()
            if password != password2:
                st.error("Passwords do not match.")
                st.stop()
            admin_username = (os.getenv("SUPERBOWL_ADMIN_USERNAME") or "").strip().lower()
            admin_password = os.getenv("SUPERBOWL_ADMIN_PASSWORD") or ""
            reserved_admin = admin_username if (admin_username and admin_password) else ""
            if reserved_admin and username.strip().lower() == reserved_admin:
                st.error("That username is reserved for the admin.")
                st.stop()
            with db.db() as conn:
                db.init_db(conn)
                is_admin = (not reserved_admin) and (not db.any_users_exist(conn))
                salt_b64, hash_b64 = security.hash_password(password)
                try:
                    user_id = db.create_user(
                        conn,
                        username=username,
                        display_name=display_name,
                        salt_b64=salt_b64,
                        password_hash_b64=hash_b64,
                        is_admin=is_admin,
                    )
                except Exception as e:
                    if db.is_username_taken_error(e):
                        st.error("That username is taken.")
                        st.stop()
                    raise
                db.log_action(conn, user_id, "register", {"is_admin": is_admin})
                st.session_state["user_id"] = user_id
                st.session_state["nav_page"] = "Home"
            st.success("Account created.")
            st.rerun()


def page_home(user: db.User | None):
    settings, squares, row_digits, col_digits = load_state()
    try:
        max_boxes_per_user = int(str(settings.get("max_boxes_per_user") or "0"))
    except ValueError:
        max_boxes_per_user = 0

    st.header("Super Bowl Squares")
    st.write(
        "Claim a box (or a few). Digits get assigned later, so pick based on vibes, not math. "
        "When scores update each quarter, we will highlight the winning square."
    )

    c1, c2, c3, c4 = st.columns(4)
    claimed = sum(1 for s in squares if s.get("owner_user_id"))
    c1.metric("Claimed", f"{claimed}/100")
    c2.metric("Price", f"${settings['price_per_square']}")
    c3.metric("Board locked", "Yes" if settings["board_locked"] else "No")
    c4.metric("Max per person", "Unlimited" if max_boxes_per_user <= 0 else str(max_boxes_per_user))

    st.subheader("Board")
    if user and not settings["board_locked"]:
        st.caption("Tap open squares (·) to select them. Tap your own squares to select them for release.")
    elif user and settings["board_locked"]:
        st.caption("Board is locked. You can still see highlights, but changes are disabled.")
    else:
        st.caption("Sign in to claim or release squares. (You can still browse the board.)")

    flash = st.session_state.pop("home_flash_message", None)
    if flash:
        st.success(str(flash))

    selected_ids = set(st.session_state.get("home_selected_square_ids", []))

    my_ids = {int(s["id"]) for s in squares if user and s.get("owner_user_id") == user.id}
    open_ids = {int(s["id"]) for s in squares if not s.get("owner_user_id")}

    def _toggle_select(sq_id: int) -> None:
        sel = set(st.session_state.get("home_selected_square_ids", []))
        if sq_id in sel:
            sel.remove(sq_id)
        else:
            sel.add(sq_id)
        st.session_state["home_selected_square_ids"] = sorted(sel)
        st.rerun()

    can_edit = bool(user) and (not settings["board_locked"])
    render_board_grid(
        squares=squares,
        row_digits=row_digits,
        col_digits=col_digits,
        team_rows=str(settings["team_rows"] or "Away"),
        team_columns=str(settings["team_columns"] or "Home"),
        grid_key_prefix="home",
        click_to_claim=False,
        on_claim=lambda _sq_id: None,
        selected_ids=selected_ids,
        on_toggle_select=_toggle_select if can_edit else None,
        allow_toggle_own=True,
        highlight_user_id=user.id if user else None,
    )

    if can_edit and user:
        selected_open = sorted([sq for sq in selected_ids if sq in open_ids])
        selected_mine = sorted([sq for sq in selected_ids if sq in my_ids])
        c1, c2, c3, c4 = st.columns([1.25, 1.15, 1, 1.2])
        current_owned = len(my_ids)
        projected_owned = max(0, current_owned + len(selected_open) - len(selected_mine))
        delta = projected_owned - current_owned
        c1.metric("Your boxes", str(projected_owned), delta=(f"{delta:+d}" if delta else None))
        c2.markdown(f"Will claim: `{len(selected_open)}`  \nWill release: `{len(selected_mine)}`")
        if c3.button("Clear selection", disabled=(len(selected_ids) == 0), use_container_width=True):
            st.session_state["home_selected_square_ids"] = []
            st.rerun()

        apply_disabled = (len(selected_open) == 0) and (len(selected_mine) == 0)
        if c4.button("Apply changes", type="primary", disabled=apply_disabled, use_container_width=True):
            if max_boxes_per_user > 0 and projected_owned > max_boxes_per_user:
                st.error(
                    f"Max is {max_boxes_per_user} squares per person. "
                    f"Your selection would leave you with {projected_owned}. Reduce claims or release more squares."
                )
                st.stop()

            claimed_ids: list[int] = []
            released_ids: list[int] = []
            skipped: list[int] = []
            skipped_due_to_limit: list[int] = []
            with db.db() as conn:
                db.init_db(conn)
                # Enforce the cap at write-time too.
                current_owned_db = db.count_user_squares(conn, user.id)
                max_setting = max_boxes_per_user
                if max_setting > 0:
                    remaining_slots = max(0, max_setting - (current_owned_db - len(selected_mine)))
                else:
                    remaining_slots = 10_000

                for sq_id in selected_open:
                    if remaining_slots <= 0:
                        skipped_due_to_limit.append(sq_id)
                        continue
                    owner = db.get_square_owner_user_id(conn, sq_id)
                    if owner is not None:
                        skipped.append(sq_id)
                        continue
                    db.set_square_owner(conn, sq_id, user.id)
                    db.log_action(conn, user.id, "claim_square", {"square_id": sq_id})
                    claimed_ids.append(sq_id)
                    remaining_slots -= 1
                for sq_id in selected_mine:
                    owner = db.get_square_owner_user_id(conn, sq_id)
                    if owner != user.id:
                        skipped.append(sq_id)
                        continue
                    db.set_square_owner(conn, sq_id, None)
                    db.log_action(conn, user.id, "release_square", {"square_id": sq_id})
                    released_ids.append(sq_id)

            st.session_state["home_selected_square_ids"] = []
            msg = []
            if claimed_ids:
                msg.append(f"claimed {len(claimed_ids)}")
            if released_ids:
                msg.append(f"released {len(released_ids)}")
            if skipped:
                msg.append(f"skipped {len(skipped)} (changed by someone else)")
            if skipped_due_to_limit:
                msg.append(f"skipped {len(skipped_due_to_limit)} (limit reached)")
            st.session_state["home_flash_message"] = "Update: " + (", ".join(msg) if msg else "no changes")
            st.rerun()

    owners = sorted({(s.get("owner_user_id"), s.get("owner_display_name")) for s in squares if s.get("owner_user_id")})
    if owners:
        st.write("Owners:")
        st.write(", ".join(sorted({str(name) for _, name in owners if name})))

    st.subheader("Digits")
    if row_digits and col_digits:
        st.write(
            f"Rows ({settings['team_rows']}): {row_digits}  |  Columns ({settings['team_columns']}): {col_digits}"
        )
    else:
        st.info("Digits have not been assigned yet (that is normal).")

    st.subheader("Quarter winners")
    if not (row_digits and col_digits):
        st.caption("Winners show up after digits are assigned and scores are entered.")
    else:
        with db.db() as conn:
            winners = []
            for q in (1, 2, 3, 4):
                score = db.get_score(conn, q)
                win_sq = game_logic.compute_winner_square_id(
                    rows_score=int(score["rows_score"]),
                    cols_score=int(score["cols_score"]),
                    row_digits=row_digits,
                    col_digits=col_digits,
                )
                win_owner = next((s.get("owner_display_name") for s in squares if int(s["id"]) == win_sq), None)
                r, c = game_logic.row_col_from_id(win_sq)
                winners.append(
                    {
                        "Quarter": q,
                        settings["team_rows"]: int(score["rows_score"]),
                        settings["team_columns"]: int(score["cols_score"]),
                        "Winning square": f"R{r} C{c} (#{win_sq})",
                        "Winner": win_owner or "(unclaimed)",
                    }
                )
        st.dataframe(pd.DataFrame(winners), use_container_width=True, hide_index=True)

    with st.expander("Recent activity", expanded=False):
        with db.db() as conn:
            rows = db.recent_audit(conn, limit=15)
        if not rows:
            st.caption("No activity yet.")
        else:
            for r in rows:
                actor = r["actor_display_name"] or "Someone"
                details = json.loads(r["details_json"]) if r["details_json"] else {}
                st.write(f"- {_ts_to_str(int(r['created_at_ts']))}: {actor} {r['action']} {details}")


def page_pick_boxes(user: db.User):
    settings, squares, row_digits, col_digits = load_state()
    if settings["board_locked"]:
        st.warning("Board is locked. Ask an admin if you need to change anything.")
        st.stop()

    st.header("Claim squares")
    st.caption("Pick a row + column, or grab a few at once.")

    flash = st.session_state.pop("flash_message", None)
    if flash:
        st.success(str(flash))

    owned_ids = {int(s["id"]) for s in squares if s.get("owner_user_id") == user.id}
    available_ids = [int(s["id"]) for s in squares if not s.get("owner_user_id")]

    c1, c2, c3 = st.columns(3)
    c1.metric("Available", str(len(available_ids)))
    c2.metric("You own", str(len(owned_ids)))
    c3.metric("Price each", f"${settings['price_per_square']}")

    st.subheader("Click-to-claim board")
    st.caption("Tap open squares (·) to select them, then hit Claim.")

    selected_ids = set(st.session_state.get("selected_square_ids", []))

    def _toggle_select(sq_id: int) -> None:
        sel = set(st.session_state.get("selected_square_ids", []))
        if sq_id in sel:
            sel.remove(sq_id)
        else:
            sel.add(sq_id)
        st.session_state["selected_square_ids"] = sorted(sel)
        st.rerun()

    render_board_grid(
        squares=squares,
        row_digits=row_digits,
        col_digits=col_digits,
        team_rows=settings["team_rows"],
        team_columns=settings["team_columns"],
        grid_key_prefix="claim",
        click_to_claim=False,
        on_claim=lambda _sq_id: None,
        selected_ids=selected_ids,
        on_toggle_select=_toggle_select,
        allow_toggle_own=False,
        highlight_user_id=user.id,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Selected", str(len(selected_ids)))
    if c2.button("Clear selection", disabled=(len(selected_ids) == 0)):
        st.session_state["selected_square_ids"] = []
        st.rerun()

    if c3.button("Claim selected", type="primary", disabled=(len(selected_ids) == 0)):
        claimed: list[int] = []
        already_taken: list[int] = []
        with db.db() as conn:
            db.init_db(conn)
            for sq_id in sorted(selected_ids):
                owner = db.get_square_owner_user_id(conn, sq_id)
                if owner is not None:
                    already_taken.append(sq_id)
                    continue
                db.set_square_owner(conn, sq_id, user.id)
                db.log_action(conn, user.id, "claim_square", {"square_id": sq_id})
                claimed.append(sq_id)
        st.session_state["selected_square_ids"] = []
        if claimed and not already_taken:
            st.session_state["flash_message"] = f"Claimed {len(claimed)} square(s)."
        elif claimed and already_taken:
            st.session_state["flash_message"] = (
                f"Claimed {len(claimed)} square(s). {len(already_taken)} were already taken."
            )
        else:
            st.session_state["flash_message"] = "No squares were claimed (they were already taken)."
        st.rerun()

    st.caption("Claimed squares will show your name on the board right away.")


def page_my_boxes(user: db.User):
    settings, squares, row_digits, col_digits = load_state()
    st.header("My squares")

    mine = [s for s in squares if s.get("owner_user_id") == user.id]
    if not mine:
        st.info("You do not own any squares yet. Head to 'Claim squares'.")
        st.stop()

    rows = []
    for s in mine:
        r, c = game_logic.row_col_from_id(int(s["id"]))
        rows.append({"Square": f"R{r} C{c} (#{s['id']})"})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if row_digits and col_digits:
        st.subheader("What digits do I have?")
        st.caption(
            f"Rows use {settings['team_rows']} last-digit; columns use {settings['team_columns']} last-digit."
        )
        enriched = []
        for s in mine:
            r, c = game_logic.row_col_from_id(int(s["id"]))
            enriched.append(
                {
                    "Square": f"R{r} C{c} (#{s['id']})",
                    f"{settings['team_rows']} digit": row_digits[r],
                    f"{settings['team_columns']} digit": col_digits[c],
                }
            )
        st.dataframe(pd.DataFrame(enriched), use_container_width=True, hide_index=True)

    if settings["board_locked"]:
        st.info("Board is locked, so squares cannot be released.")
        return

    st.subheader("Release a square")
    options = [f"#{int(s['id'])}" for s in mine]
    pick = st.selectbox("Pick one", options)
    if st.button("Release it"):
        sq_id = int(pick.lstrip("#"))
        with db.db() as conn:
            db.init_db(conn)
            owner = db.get_square_owner_user_id(conn, sq_id)
            if owner != user.id:
                st.error("That square is not yours anymore.")
                st.stop()
            db.set_square_owner(conn, sq_id, None)
            db.log_action(conn, user.id, "release_square", {"square_id": sq_id})
        st.success("Released.")
        st.rerun()


def page_scores(user: db.User | None):
    settings, squares, row_digits, col_digits = load_state()
    st.header("Scores")
    st.caption("Admin enters quarter-end scores. Everyone can view.")

    if row_digits and col_digits:
        st.info(
            f"Winner is: row digit = {settings['team_rows']} last digit, col digit = {settings['team_columns']} last digit."
        )
    else:
        st.warning("Digits are not assigned yet, so winners cannot be computed.")

    with db.db() as conn:
        scores = [db.get_score(conn, q) for q in (1, 2, 3, 4)]

    table = []
    for s in scores:
        table.append(
            {
                "Quarter": int(s["quarter"]),
                settings["team_rows"]: int(s["rows_score"]),
                settings["team_columns"]: int(s["cols_score"]),
                "Updated": _ts_to_str(int(s["updated_at_ts"])),
            }
        )
    st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)

    if not (user and user.is_admin):
        return

    st.subheader("Update a quarter")
    with st.form("update_score"):
        quarter = st.selectbox("Quarter", [1, 2, 3, 4], index=0)
        rows_score = st.number_input(f"{settings['team_rows']} score", min_value=0, max_value=99, value=0, step=1)
        cols_score = st.number_input(f"{settings['team_columns']} score", min_value=0, max_value=99, value=0, step=1)
        submitted = st.form_submit_button("Save score")
    if submitted:
        with db.db() as conn:
            db.init_db(conn)
            db.set_score(conn, quarter=int(quarter), rows_score=int(rows_score), cols_score=int(cols_score), updated_by_user_id=user.id)
            db.log_action(
                conn,
                user.id,
                "update_score",
                {"quarter": int(quarter), "rows_score": int(rows_score), "cols_score": int(cols_score)},
            )
        st.success("Saved.")
        st.rerun()

    if row_digits and col_digits:
        st.subheader("Winners (based on current scores)")
        winners = []
        for q in (1, 2, 3, 4):
            with db.db() as conn:
                score = db.get_score(conn, q)
            win_sq = game_logic.compute_winner_square_id(
                rows_score=int(score["rows_score"]),
                cols_score=int(score["cols_score"]),
                row_digits=row_digits,
                col_digits=col_digits,
            )
            win_owner = next((s.get("owner_display_name") for s in squares if int(s["id"]) == win_sq), None)
            r, c = game_logic.row_col_from_id(win_sq)
            winners.append(
                {"Quarter": q, "Winning square": f"R{r} C{c} (#{win_sq})", "Winner": win_owner or "(unclaimed)"}
            )
        st.dataframe(pd.DataFrame(winners), use_container_width=True, hide_index=True)


def page_admin(user: db.User):
    require_admin(user)
    settings, squares, row_digits, col_digits = load_state()

    st.header("Admin")
    st.caption("You are the referee. No pressure.")

    st.subheader("Game setup")
    with st.form("setup"):
        team_rows = st.text_input("Rows team name", value=settings["team_rows"])
        team_cols = st.text_input("Columns team name", value=settings["team_columns"])
        price = st.number_input("Price per square", min_value=0, max_value=1000, value=int(settings["price_per_square"]), step=1)
        try:
            max_boxes = int(str(settings.get("max_boxes_per_user") or "0"))
        except ValueError:
            max_boxes = 0
        max_boxes = st.number_input(
            "Max squares per person (0 = unlimited)",
            min_value=0,
            max_value=100,
            value=int(max_boxes),
            step=1,
        )
        board_locked = st.checkbox("Lock board (prevents claiming/releasing)", value=bool(settings["board_locked"]))
        submitted = st.form_submit_button("Save settings")
    if submitted:
        with db.db() as conn:
            db.init_db(conn)
            db.set_setting(conn, "team_rows", team_rows.strip() or "Away")
            db.set_setting(conn, "team_columns", team_cols.strip() or "Home")
            db.set_setting(conn, "price_per_square", str(int(price)))
            db.set_setting(conn, "max_boxes_per_user", str(int(max_boxes)))
            db.set_setting(conn, "board_locked", "1" if board_locked else "0")
            db.log_action(
                conn,
                user.id,
                "update_settings",
                {
                    "team_rows": team_rows,
                    "team_columns": team_cols,
                    "price": int(price),
                    "max_boxes_per_user": int(max_boxes),
                    "board_locked": board_locked,
                },
            )
        st.success("Saved.")
        st.rerun()

    st.subheader("Digits assignment")
    if row_digits and col_digits:
        st.write(f"Rows digits: {row_digits}")
        st.write(f"Columns digits: {col_digits}")
    else:
        st.info("Digits not assigned yet.")

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Randomize rows + columns"):
            digits = list(range(10))
            rd = digits[:]
            cd = digits[:]
            random.shuffle(rd)
            random.shuffle(cd)
            with db.db() as conn:
                db.init_db(conn)
                db.set_setting(conn, "row_digits_json", game_logic.digits_to_json(rd))
                db.set_setting(conn, "col_digits_json", game_logic.digits_to_json(cd))
                db.log_action(conn, user.id, "assign_digits", {"row_digits": rd, "col_digits": cd})
            st.success("Digits assigned.")
            st.rerun()
    with c2:
        if st.button("Randomize rows only"):
            digits = list(range(10))
            rd = digits[:]
            random.shuffle(rd)
            cd = col_digits if col_digits else digits[:]
            if not col_digits:
                random.shuffle(cd)
            with db.db() as conn:
                db.init_db(conn)
                db.set_setting(conn, "row_digits_json", game_logic.digits_to_json(rd))
                db.set_setting(conn, "col_digits_json", game_logic.digits_to_json(cd))
                db.log_action(conn, user.id, "assign_digits_rows_only", {"row_digits": rd, "col_digits": cd})
            st.success("Rows digits randomized.")
            st.rerun()
    with c3:
        if st.button("Randomize columns only"):
            digits = list(range(10))
            cd = digits[:]
            random.shuffle(cd)
            rd = row_digits if row_digits else digits[:]
            if not row_digits:
                random.shuffle(rd)
            with db.db() as conn:
                db.init_db(conn)
                db.set_setting(conn, "row_digits_json", game_logic.digits_to_json(rd))
                db.set_setting(conn, "col_digits_json", game_logic.digits_to_json(cd))
                db.log_action(conn, user.id, "assign_digits_cols_only", {"row_digits": rd, "col_digits": cd})
            st.success("Columns digits randomized.")
            st.rerun()

    st.caption("Digits map score last-digits (0-9) to the board edges. Randomize once you're ready.")

    if st.button("Clear digits", type="secondary"):
        with db.db() as conn:
            db.init_db(conn)
            db.set_setting(conn, "row_digits_json", "")
            db.set_setting(conn, "col_digits_json", "")
            db.log_action(conn, user.id, "clear_digits", {})
        st.success("Cleared.")
        st.rerun()

    st.subheader("Manual square reassignment")
    taken = [s for s in squares if s.get("owner_user_id")]
    if not taken:
        st.caption("No claimed squares yet.")
    else:
        with db.db() as conn:
            users = db.list_users_basic(conn)
        user_map = {int(u["id"]): str(u["display_name"]) for u in users}
        sq = st.selectbox(
            "Pick a claimed square",
            [f"#{int(s['id'])} ({s.get('owner_display_name')})" for s in taken],
        )
        new_owner = st.selectbox(
            "Reassign to",
            ["(unclaimed)"] + [f"{name} (id={uid})" for uid, name in sorted(user_map.items(), key=lambda x: x[1].lower())],
        )
        if st.button("Reassign square"):
            sq_id = int(sq.split()[0].lstrip("#"))
            owner_id = None
            if new_owner != "(unclaimed)":
                owner_id = int(new_owner.split("id=")[-1].rstrip(")"))
            with db.db() as conn:
                db.init_db(conn)
                db.set_square_owner(conn, sq_id, owner_id)
                db.log_action(conn, user.id, "reassign_square", {"square_id": sq_id, "new_owner_user_id": owner_id})
            st.success("Done.")
            st.rerun()

    st.subheader("Reset board (keeps users)")
    st.caption("Use this if you want to reuse the app next year without deleting accounts.")
    if st.button("Reset squares + scores", type="secondary"):
        with db.db() as conn:
            db.init_db(conn)
            db.reset_board_keep_users(conn)
            db.log_action(conn, user.id, "reset_board", {})
        st.success("Reset complete.")
        st.rerun()

    st.subheader("Database maintenance")
    with st.expander("Database tools", expanded=False):
        if db.using_postgres():
            st.caption("Backend: Postgres/Neon (`DATABASE_URL`)")
            st.info("DB file actions are disabled for Postgres. Use Neon backups or pg_dump if you need exports.")
        else:
            db_file = db.db_path()
            st.caption(f"Backend: SQLite (`{db_file}`)")
            if db_file.exists():
                try:
                    size_kb = db_file.stat().st_size / 1024
                    st.caption(f"DB size: {size_kb:,.1f} KB")
                except Exception:
                    pass

                try:
                    raw = db_file.read_bytes()
                    st.download_button(
                        "Download DB backup",
                        data=raw,
                        file_name="squares.db",
                        mime="application/x-sqlite3",
                        use_container_width=True,
                    )
                except Exception:
                    st.warning("Could not read DB file for download (permissions?).")
            else:
                st.info("DB file not found yet (it will be created automatically on first use).")

        c1, c2 = st.columns(2)
        with c1:
            vacuum_disabled = db.using_postgres()
            if st.button("VACUUM / optimize", use_container_width=True, disabled=vacuum_disabled):
                with db.db() as conn:
                    db.vacuum_optimize(conn)
                    db.log_action(conn, user.id, "db_vacuum", {})
                st.success("Database optimized.")
                st.rerun()
            if vacuum_disabled:
                st.caption("VACUUM is SQLite-only.")
        with c2:
            keep_audit = st.number_input("Keep last N audit rows", min_value=0, max_value=50000, value=500, step=50)
            if st.button("Prune audit log", use_container_width=True):
                with db.db() as conn:
                    db.init_db(conn)
                    db.prune_audit_log(conn, keep_last=int(keep_audit))
                    db.log_action(conn, user.id, "prune_audit_log", {"keep": int(keep_audit)})
                st.success("Audit log pruned.")
                st.rerun()

        st.divider()
        if db.using_postgres():
            st.caption("Danger zone is disabled for Postgres. Use Neon console if you need to wipe the DB.")
        else:
            st.caption("Danger zone: deletes the DB file and starts fresh (users + board + history).")
            confirm = st.text_input("Type RESET to confirm", value="", placeholder="RESET")
            if st.button("Delete DB file and recreate", type="primary", disabled=(confirm.strip() != "RESET")):
                # Clear session so we don't keep a stale user_id.
                for k in ("user_id", "nav_page", "home_selected_square_ids", "selected_square_ids"):
                    st.session_state.pop(k, None)

                paths = [db_file]
                for suffix in ("-wal", "-shm", "-journal"):
                    paths.append(Path(str(db_file) + suffix))
                for p in paths:
                    try:
                        if p.exists():
                            p.unlink()
                    except Exception:
                        pass
                st.success("DB deleted. Reloading…")
                st.rerun()


def main():
    # Local dev convenience: load `superbowl_squares/.env` if present.
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parent / ".env")

    st.set_page_config(page_title="Super Bowl Squares", layout="wide")
    st.markdown(_GLOBAL_CSS, unsafe_allow_html=True)

    # Streamlit secrets → env bridge (so `db.py` can read DATABASE_URL / admin creds).
    try:
        secrets = st.secrets  # type: ignore[attr-defined]
        for key in (
            "DATABASE_URL",
            "NEON_DATABASE_URL",
            "POSTGRES_URL",
            "POSTGRES_URL_NON_POOLING",
            "SUPERBOWL_ADMIN_USERNAME",
            "SUPERBOWL_ADMIN_PASSWORD",
            "SUPERBOWL_ADMIN_DISPLAY_NAME",
            "SUPERBOWL_SQUARES_DB_PATH",
        ):
            if key in secrets and str(secrets[key]).strip():
                os.environ.setdefault(key, str(secrets[key]))
    except Exception:
        pass

    # Initialize DB early (creates file + tables)
    with db.db() as conn:
        db.init_db(conn)
        db.ensure_admin_from_env(conn)

    user = None
    if st.session_state.get("user_id"):
        with db.db() as conn:
            user = db.get_user(conn, int(st.session_state["user_id"]))

    # Auth-first: if you're not signed in, go straight to Sign in / Register.
    if not user:
        page_auth()
        return

    valid_pages = ["Home", "Sign in / Register", "Scores", "Admin"]
    if st.session_state.get("nav_page") not in valid_pages:
        st.session_state["nav_page"] = "Home"

    with st.sidebar:
        st.title("Squares")
        if user:
            st.write(f"Signed in as: {user.display_name}")
            if st.button("Sign out"):
                st.session_state.pop("user_id", None)
                st.rerun()
        else:
            st.write("Not signed in.")

        page = st.radio(
            "Go to",
            options=["Home", "Sign in / Register", "Scores", "Admin"],
            key="nav_page",
        )

    if page == "Sign in / Register":
        page_auth()
        return

    if page == "Home":
        page_home(user)
        return

    if page == "Scores":
        page_scores(user)
        return

    if page == "Admin":
        page_admin(require_login())
        return


if __name__ == "__main__":
    main()
