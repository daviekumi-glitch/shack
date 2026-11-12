"""Persistent memory for SHACK: conversation history, facts, tasks, reminders."""

from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    session TEXT    NOT NULL,
    role    TEXT    NOT NULL,
    content TEXT    NOT NULL,
    ts      REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session, id);

CREATE TABLE IF NOT EXISTS facts (
    key    TEXT PRIMARY KEY,
    value  TEXT NOT NULL,
    source TEXT DEFAULT 'agent',
    ts     REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    done  INTEGER NOT NULL DEFAULT 0,
    ts    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    text     TEXT NOT NULL,
    due_ts   REAL NOT NULL,
    fired    INTEGER NOT NULL DEFAULT 0,
    ts       REAL NOT NULL
);
"""

SUMMARY_KEY = "rolling_summary"
NAME_KEY = "user_name"


class Memory:
    """Thread-safe SQLite store shared by the agent and the reminder watcher."""

    def __init__(self, path: Path, session: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or time.strftime("session-%Y%m%d-%H%M%S")
        self._lock = threading.RLock()  # reentrant: older_messages() re-reads a count
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ chat
    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (session, role, content, ts) VALUES (?,?,?,?)",
                (self.session, role, content, time.time()),
            )
            self._conn.commit()

    def recent_messages(self, limit: int = 24) -> list[dict[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages WHERE session=? "
                "ORDER BY id DESC LIMIT ?",
                (self.session, limit),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    def message_count(self, session: str | None = None) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE session=?",
                (session or self.session,),
            ).fetchone()
        return int(row["n"])

    def older_messages(self, keep: int) -> list[dict[str, str]]:
        """Everything except the newest `keep` messages of this session."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages WHERE session=? "
                "ORDER BY id ASC LIMIT ?",
                (self.session, max(0, self.message_count() - keep)),
            ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def trim_messages(self, keep: int) -> int:
        """Delete this session's messages older than the newest `keep`."""
        with self._lock:
            cur = self._conn.execute(
                "DELETE FROM messages WHERE session=? AND id NOT IN ("
                "  SELECT id FROM messages WHERE session=? ORDER BY id DESC LIMIT ?"
                ")",
                (self.session, self.session, keep),
            )
            self._conn.commit()
        return cur.rowcount

    def reset_conversation(self) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM messages WHERE session=?", (self.session,))
            self._conn.commit()

    # ----------------------------------------------------------------- facts
    def set_fact(self, key: str, value: str, source: str = "agent") -> None:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            self._conn.execute(
                "INSERT INTO facts (key, value, source, ts) VALUES (?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "source=excluded.source, ts=excluded.ts",
                (key, value.strip(), source, time.time()),
            )
            self._conn.commit()

    def get_fact(self, key: str) -> str | None:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM facts WHERE key=?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def delete_fact(self, key: str) -> bool:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            cur = self._conn.execute("DELETE FROM facts WHERE key=?", (key,))
            self._conn.commit()
        return cur.rowcount > 0

    def all_facts(self, limit: int = 60) -> list[tuple[str, str]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM facts WHERE key != ? ORDER BY ts DESC LIMIT ?",
                (SUMMARY_KEY, limit),
            ).fetchall()
        return [(r["key"], r["value"]) for r in rows]

    def search_facts(self, query: str, limit: int = 15) -> list[tuple[str, str]]:
        like = f"%{query.strip()}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT key, value FROM facts WHERE (key LIKE ? OR value LIKE ?) "
                "AND key != ? ORDER BY ts DESC LIMIT ?",
                (like, like, SUMMARY_KEY, limit),
            ).fetchall()
        return [(r["key"], r["value"]) for r in rows]

    def set_summary(self, text: str) -> None:
        self.set_fact(SUMMARY_KEY, text, source="system")

    def get_summary(self) -> str:
        return self.get_fact(SUMMARY_KEY) or ""

    # ----------------------------------------------------------------- tasks
    def add_task(self, title: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tasks (title, done, ts) VALUES (?,0,?)",
                (title.strip(), time.time()),
            )
            self._conn.commit()
        return int(cur.lastrowid)

    def list_tasks(self, include_done: bool = False) -> list[dict[str, Any]]:
        query = "SELECT id, title, done FROM tasks"
        if not include_done:
            query += " WHERE done=0"
        query += " ORDER BY done, id"
        with self._lock:
            rows = self._conn.execute(query).fetchall()
        return [dict(r) for r in rows]

    def complete_task(self, task_id: int | None = None, match: str | None = None) -> str:
        with self._lock:
            if task_id is not None:
                cur = self._conn.execute(
                    "UPDATE tasks SET done=1 WHERE id=? AND done=0", (task_id,)
                )
            elif match:
                cur = self._conn.execute(
                    "UPDATE tasks SET done=1 WHERE done=0 AND title LIKE ?",
                    (f"%{match}%",),
                )
            else:
                return "No task given."
            self._conn.commit()
        if cur.rowcount:
            return f"Done, closed {cur.rowcount} task(s)."
        return "I could not find an open task like that."

    # ------------------------------------------------------------- reminders
    def add_reminder(self, text: str, due_ts: float) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO reminders (text, due_ts, fired, ts) VALUES (?,?,0,?)",
                (text.strip(), due_ts, time.time()),
            )
            self._conn.commit()
        return int(cur.lastrowid)

    def due_reminders(self, now: float | None = None) -> list[dict[str, Any]]:
        now = now if now is not None else time.time()
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, text, due_ts FROM reminders WHERE fired=0 AND due_ts<=? "
                "ORDER BY due_ts",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_reminder_fired(self, reminder_id: int) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE reminders SET fired=1 WHERE id=?", (reminder_id,)
            )
            self._conn.commit()

    def pending_reminders(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, text, due_ts FROM reminders WHERE fired=0 ORDER BY due_ts"
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
