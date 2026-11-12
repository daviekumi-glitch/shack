"""A dependency-free memory store used when SQLite is unavailable.

Android builds of Python sometimes ship without the sqlite3 module. This
implements the same surface as `Memory` on top of a JSON file, so SHACK keeps
its facts, tasks, reminders and conversation history either way.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

SUMMARY_KEY = "rolling_summary"

_EMPTY = {
    "sessions": {},
    "facts": {},
    "tasks": [],
    "reminders": [],
    "next_task": 1,
    "next_reminder": 1,
}


class SimpleMemory:
    def __init__(self, path: Path, session: str | None = None) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session or time.strftime("session-%Y%m%d-%H%M%S")
        self._lock = threading.RLock()
        self._data = self._read()

    # ------------------------------------------------------------- plumbing
    def _read(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raw = {}
        data = json.loads(json.dumps(_EMPTY))  # deep copy of the defaults
        data.update({k: v for k, v in raw.items() if k in data})
        return data

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(self._data), encoding="utf-8")
            tmp.replace(self.path)
        except OSError:
            pass

    def _messages(self) -> list[dict[str, Any]]:
        return self._data["sessions"].setdefault(self.session, [])

    # ------------------------------------------------------------------ chat
    def add_message(self, role: str, content: str) -> None:
        with self._lock:
            self._messages().append({"role": role, "content": content, "ts": time.time()})
            self._save()

    def recent_messages(self, limit: int = 24) -> list[dict[str, str]]:
        with self._lock:
            rows = self._messages()[-limit:]
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def message_count(self, session: str | None = None) -> int:
        with self._lock:
            key = session or self.session
            return len(self._data["sessions"].get(key, []))

    def older_messages(self, keep: int) -> list[dict[str, str]]:
        with self._lock:
            rows = self._messages()
            cut = max(0, len(rows) - keep)
            rows = rows[:cut]
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def trim_messages(self, keep: int) -> int:
        with self._lock:
            rows = self._messages()
            cut = max(0, len(rows) - keep)
            del rows[:cut]
            self._save()
        return cut

    def reset_conversation(self) -> None:
        with self._lock:
            self._data["sessions"][self.session] = []
            self._save()

    # ----------------------------------------------------------------- facts
    def set_fact(self, key: str, value: str, source: str = "agent") -> None:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            self._data["facts"][key] = {
                "value": value.strip(),
                "source": source,
                "ts": time.time(),
            }
            self._save()

    def get_fact(self, key: str) -> str | None:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            row = self._data["facts"].get(key)
        return row["value"] if row else None

    def delete_fact(self, key: str) -> bool:
        key = key.strip().lower().replace(" ", "_")
        with self._lock:
            existed = self._data["facts"].pop(key, None) is not None
            if existed:
                self._save()
        return existed

    def all_facts(self, limit: int = 60) -> list[tuple[str, str]]:
        with self._lock:
            rows = [
                (k, v["value"])
                for k, v in self._data["facts"].items()
                if k != SUMMARY_KEY
            ]
        rows.sort(key=lambda item: self._data["facts"][item[0]]["ts"], reverse=True)
        return rows[:limit]

    def search_facts(self, query: str, limit: int = 15) -> list[tuple[str, str]]:
        needle = (query or "").strip().lower()
        with self._lock:
            rows = [
                (k, v["value"])
                for k, v in self._data["facts"].items()
                if k != SUMMARY_KEY
                and (needle in k.lower() or needle in v["value"].lower())
            ]
        return sorted(rows)[:limit]

    def set_summary(self, text: str) -> None:
        self.set_fact(SUMMARY_KEY, text, source="system")

    def get_summary(self) -> str:
        return self.get_fact(SUMMARY_KEY) or ""

    # ----------------------------------------------------------------- tasks
    def add_task(self, title: str) -> int:
        with self._lock:
            task_id = int(self._data["next_task"])
            self._data["next_task"] = task_id + 1
            self._data["tasks"].append(
                {"id": task_id, "title": title.strip(), "done": 0, "ts": time.time()}
            )
            self._save()
        return task_id

    def list_tasks(self, include_done: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            tasks = [dict(t) for t in self._data["tasks"] if include_done or not t["done"]]
        return tasks

    def complete_task(self, task_id: int | None = None, match: str | None = None) -> str:
        closed = 0
        with self._lock:
            for task in self._data["tasks"]:
                if task["done"]:
                    continue
                if task_id is not None and task["id"] == task_id:
                    task["done"] = 1
                    closed += 1
                elif match and match.lower() in task["title"].lower():
                    task["done"] = 1
                    closed += 1
            if closed:
                self._save()
        if closed:
            return f"Done, closed {closed} task(s)."
        return "I could not find an open task like that."

    # ------------------------------------------------------------- reminders
    def add_reminder(self, text: str, due_ts: float) -> int:
        with self._lock:
            reminder_id = int(self._data["next_reminder"])
            self._data["next_reminder"] = reminder_id + 1
            self._data["reminders"].append(
                {
                    "id": reminder_id,
                    "text": text.strip(),
                    "due_ts": float(due_ts),
                    "fired": 0,
                    "ts": time.time(),
                }
            )
            self._save()
        return reminder_id

    def due_reminders(self, now: float | None = None) -> list[dict[str, Any]]:
        now = now if now is not None else time.time()
        with self._lock:
            rows = [
                dict(r)
                for r in self._data["reminders"]
                if not r["fired"] and r["due_ts"] <= now
            ]
        return sorted(rows, key=lambda r: r["due_ts"])

    def mark_reminder_fired(self, reminder_id: int) -> None:
        with self._lock:
            for reminder in self._data["reminders"]:
                if reminder["id"] == reminder_id:
                    reminder["fired"] = 1
            self._save()

    def pending_reminders(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = [dict(r) for r in self._data["reminders"] if not r["fired"]]
        return sorted(rows, key=lambda r: r["due_ts"])

    def close(self) -> None:
        with self._lock:
            self._save()
