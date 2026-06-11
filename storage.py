import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()


def init_db():
    with _conn() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS birthdays (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                remind_at TEXT,
                repeat TEXT NOT NULL DEFAULT 'once',
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_notes_user ON notes(user_id);
            CREATE INDEX IF NOT EXISTS idx_bdays_user ON birthdays(user_id);
            """
        )


def add_birthday(user_id, name, date_str):
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO birthdays (user_id, name, date) VALUES (?, ?, ?)",
            (user_id, name, date_str),
        )
        return cur.lastrowid


def get_birthdays(user_id):
    with _conn() as con:
        rows = con.execute(
            "SELECT id, name, date FROM birthdays WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def delete_birthday(user_id, bday_id):
    with _conn() as con:
        con.execute(
            "DELETE FROM birthdays WHERE user_id = ? AND id = ?",
            (user_id, bday_id),
        )


def days_until(date_str):
    bday = datetime.strptime(date_str, "%d.%m.%Y")
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    next_bday = bday.replace(year=today.year)
    if next_bday < today:
        next_bday = next_bday.replace(year=today.year + 1)
    return (next_bday - today).days


def add_note(user_id, text, remind_at=None, repeat="once"):
    created = datetime.now().strftime("%d.%m.%Y %H:%M")
    with _conn() as con:
        cur = con.execute(
            "INSERT INTO notes (user_id, text, remind_at, repeat, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, text, remind_at, repeat, created),
        )
        note_id = cur.lastrowid
        row = con.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        return dict(row) if row else None


def get_notes(user_id, only_active=False):
    sql = "SELECT * FROM notes WHERE user_id = ?"
    params = [user_id]
    if only_active:
        sql += " AND done = 0"
    sql += " ORDER BY id"
    with _conn() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def search_notes(user_id, query):
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notes WHERE user_id = ? AND text LIKE ? ORDER BY id",
            (user_id, f"%{query}%"),
        ).fetchall()
        return [dict(r) for r in rows]


def update_note_text(user_id, note_id, text):
    with _conn() as con:
        con.execute(
            "UPDATE notes SET text = ? WHERE user_id = ? AND id = ?",
            (text, user_id, note_id),
        )


def mark_note_done(user_id, note_id):
    with _conn() as con:
        con.execute(
            "UPDATE notes SET done = 1 WHERE user_id = ? AND id = ?",
            (user_id, note_id),
        )


def delete_note(user_id, note_id):
    with _conn() as con:
        con.execute(
            "DELETE FROM notes WHERE user_id = ? AND id = ?",
            (user_id, note_id),
        )


def get_pending_reminders():
    now = datetime.now()
    fired = []
    with _conn() as con:
        rows = con.execute(
            "SELECT * FROM notes WHERE remind_at IS NOT NULL AND done = 0"
        ).fetchall()

        for r in rows:
            remind_time = datetime.strptime(r["remind_at"], "%d.%m.%Y %H:%M")
            if remind_time > now:
                continue

            note = dict(r)
            fired.append((r["user_id"], note))

            if r["repeat"] == "daily":
                next_time = (remind_time + timedelta(days=1)).strftime(
                    "%d.%m.%Y %H:%M"
                )
                con.execute(
                    "UPDATE notes SET remind_at = ? WHERE id = ?",
                    (next_time, r["id"]),
                )
            elif r["repeat"] == "weekly":
                next_time = (remind_time + timedelta(days=7)).strftime(
                    "%d.%m.%Y %H:%M"
                )
                con.execute(
                    "UPDATE notes SET remind_at = ? WHERE id = ?",
                    (next_time, r["id"]),
                )
            else:
                con.execute(
                    "UPDATE notes SET done = 1 WHERE id = ?", (r["id"],)
                )
    return fired


def export_notes_text(user_id):
    notes = get_notes(user_id)
    if not notes:
        return ""
    lines = []
    for n in notes:
        status = "[x]" if n["done"] else "[ ]"
        remind = f" @ {n['remind_at']}" if n["remind_at"] else ""
        repeat = f" ({n['repeat']})" if n["repeat"] != "once" else ""
        lines.append(f"{status} #{n['id']} {n['text']}{remind}{repeat}")
    return "\n".join(lines)
