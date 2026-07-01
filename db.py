"""
db.py — all SQLite access lives here.

Tables:
- members:   everyone the bot has seen talk, plus last_seen for /active
- warnings:  warning count per user per group
- rules:     one rules text per group
- reminders: scheduled reminders (handled by the job queue)
"""

import sqlite3
import time
import os

# On Railway, the local file system resets every time you deploy!
# By using os.getenv("DB_PATH"), we can tell Railway to store the database on a permanent Volume (e.g. /data/bot.db)
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "bot.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS members (
            chat_id INTEGER,
            user_id INTEGER,
            username TEXT,
            first_name TEXT,
            last_seen INTEGER,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS warnings (
            chat_id INTEGER,
            user_id INTEGER,
            count INTEGER DEFAULT 0,
            PRIMARY KEY (chat_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS rules (
            chat_id INTEGER PRIMARY KEY,
            text TEXT
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            chat_id INTEGER PRIMARY KEY,
            expiry_time INTEGER
        );
    """)
    conn.commit()
    conn.close()


# ---------- members ----------
def save_member(chat_id: int, user_id: int, username, first_name):
    conn = get_conn()
    conn.execute(
        """INSERT INTO members (chat_id, user_id, username, first_name, last_seen)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(chat_id, user_id) DO UPDATE SET
             username=excluded.username,
             first_name=excluded.first_name,
             last_seen=excluded.last_seen""",
        (chat_id, user_id, username, first_name, int(time.time())),
    )
    conn.commit()
    conn.close()


def get_members(chat_id: int):
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, username, first_name, last_seen FROM members WHERE chat_id = ?",
        (chat_id,),
    ).fetchall()
    conn.close()
    return rows


def get_active_members(chat_id: int, since_seconds: int):
    cutoff = int(time.time()) - since_seconds
    conn = get_conn()
    rows = conn.execute(
        "SELECT user_id, username, first_name, last_seen FROM members WHERE chat_id = ? AND last_seen >= ?",
        (chat_id, cutoff),
    ).fetchall()
    conn.close()
    return rows


# ---------- warnings ----------
def add_warning(chat_id: int, user_id: int) -> int:
    """Increments warning count, returns the new count."""
    conn = get_conn()
    conn.execute(
        """INSERT INTO warnings (chat_id, user_id, count) VALUES (?, ?, 1)
           ON CONFLICT(chat_id, user_id) DO UPDATE SET count = count + 1""",
        (chat_id, user_id),
    )
    conn.commit()
    row = conn.execute(
        "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    conn.close()
    return row["count"]


def get_warnings(chat_id: int, user_id: int) -> int:
    conn = get_conn()
    row = conn.execute(
        "SELECT count FROM warnings WHERE chat_id = ? AND user_id = ?",
        (chat_id, user_id),
    ).fetchone()
    conn.close()
    return row["count"] if row else 0


def reset_warnings(chat_id: int, user_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM warnings WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
    conn.commit()
    conn.close()


# ---------- rules ----------
def set_rules(chat_id: int, text: str):
    conn = get_conn()
    conn.execute(
        """INSERT INTO rules (chat_id, text) VALUES (?, ?)
           ON CONFLICT(chat_id) DO UPDATE SET text = excluded.text""",
        (chat_id, text),
    )
    conn.commit()
    conn.close()


def get_rules(chat_id: int):
    conn = get_conn()
    row = conn.execute("SELECT text FROM rules WHERE chat_id = ?", (chat_id,)).fetchone()
    conn.close()
    return row["text"] if row else None


# ---------- subscriptions ----------
def add_subscription(chat_id: int, days: int):
    conn = get_conn()
    now = int(time.time())
    
    # Check if there is already an active subscription to extend it
    row = conn.execute("SELECT expiry_time FROM subscriptions WHERE chat_id = ?", (chat_id,)).fetchone()
    if row and row["expiry_time"] > now:
        expiry = row["expiry_time"] + (days * 86400)
    else:
        expiry = now + (days * 86400)
        
    conn.execute(
        """INSERT INTO subscriptions (chat_id, expiry_time) VALUES (?, ?)
           ON CONFLICT(chat_id) DO UPDATE SET expiry_time = excluded.expiry_time""",
        (chat_id, expiry),
    )
    conn.commit()
    conn.close()


def is_subscribed(chat_id: int) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT expiry_time FROM subscriptions WHERE chat_id = ?", (chat_id,)).fetchone()
    conn.close()
    if not row:
        return False
    return row["expiry_time"] > int(time.time())
