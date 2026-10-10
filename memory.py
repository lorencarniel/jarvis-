import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "jarvis_brain.db"


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            content TEXT NOT NULL,
            importance INTEGER DEFAULT 5,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT,
            due_time TEXT,
            recurring TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# --- Memory ---

def save_memory(category, content, importance=5):
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO memories (category, content, importance, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (category, content, importance, now, now)
    )
    conn.commit()
    conn.close()


def get_memories(category=None, limit=50):
    conn = get_db()
    if category:
        rows = conn.execute(
            "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (category, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY importance DESC, updated_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def search_memories(query, limit=10):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM memories WHERE content LIKE ? ORDER BY importance DESC LIMIT ?",
        (f"%{query}%", limit)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_memory(memory_id):
    conn = get_db()
    conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
    conn.commit()
    conn.close()


# --- Conversations ---

def save_message(role, content):
    conn = get_db()
    conn.execute(
        "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_conversations(limit=20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM conversations ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def get_conversation_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    conn.close()
    return count


# --- Tasks ---

def create_task(title, description="", due_date=None, due_time=None, recurring=None):
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO tasks (title, description, due_date, due_time, recurring, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (title, description, due_date, due_time, recurring, now)
    )
    task_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return task_id


def get_tasks(status="pending"):
    conn = get_db()
    if status == "all":
        rows = conn.execute("SELECT * FROM tasks ORDER BY due_date ASC, due_time ASC").fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE status = ? ORDER BY due_date ASC, due_time ASC",
            (status,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def complete_task(task_id):
    conn = get_db()
    conn.execute(
        "UPDATE tasks SET status = 'completed', completed_at = ? WHERE id = ?",
        (datetime.now().isoformat(), task_id)
    )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()


# --- Config ---

def get_config(key, default=None):
    conn = get_db()
    row = conn.execute("SELECT value FROM config WHERE key = ?", (key,)).fetchone()
    conn.close()
    if row:
        return row[0]
    return default


def set_config(key, value):
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()
