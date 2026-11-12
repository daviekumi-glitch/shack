"""Long-term memory, tasks and reminders as tools."""

from __future__ import annotations

import time
from datetime import datetime

from .registry import ToolContext, ToolError, ToolRegistry


def remember_fact(ctx: ToolContext, key: str, value: str) -> str:
    key = (key or "").strip()
    if not key or not (value or "").strip():
        raise ToolError("need both a short key and a value")
    ctx.memory.set_fact(key, value)
    return f"Remembered: {key} = {value}"


def recall_facts(ctx: ToolContext, query: str = "") -> str:
    query = (query or "").strip()
    rows = ctx.memory.search_facts(query) if query else ctx.memory.all_facts()
    if not rows:
        return "Nothing stored about that yet."
    return "\n".join(f"- {k}: {v}" for k, v in rows)


def forget_fact(ctx: ToolContext, key: str) -> str:
    return (
        f"Forgotten: {key}"
        if ctx.memory.delete_fact(key)
        else "I had nothing stored under that name."
    )


def add_task(ctx: ToolContext, title: str) -> str:
    title = (title or "").strip()
    if not title:
        raise ToolError("the task needs a title")
    task_id = ctx.memory.add_task(title)
    return f"Task #{task_id} saved: {title}"


def list_tasks(ctx: ToolContext, include_done: bool = False) -> str:
    tasks = ctx.memory.list_tasks(include_done=bool(include_done))
    if not tasks:
        return "No open tasks. Clean slate."
    return "\n".join(
        f"{'✓' if t['done'] else '•'} #{t['id']} {t['title']}" for t in tasks
    )


def complete_task(ctx: ToolContext, task_id: int | None = None, title_match: str = "") -> str:
    if task_id is None and not title_match:
        raise ToolError("give a task id or part of its title")
    return ctx.memory.complete_task(task_id=task_id, match=title_match or None)


def _parse_when(when: str) -> float:
    """Accept ISO timestamps, 'HH:MM', or relative words like '20 minutes'."""
    when = (when or "").strip()
    if not when:
        raise ToolError("say when the reminder should fire")
    rel = when.lower().replace("in ", "", 1)
    parts = rel.split()
    if len(parts) == 2:
        unit = parts[1].rstrip("s")
        try:
            amount = float(parts[0])
        except ValueError:
            amount = None
        factors = {"second": 1, "sec": 1, "minute": 60, "min": 60, "hour": 3600,
                   "hr": 3600, "day": 86400, "week": 604800}
        if amount and unit in factors:
            return time.time() + amount * factors[unit]

    cleaned = when.replace("Z", "+00:00")
    for parse in (datetime.fromisoformat,):
        try:
            parsed = parse(cleaned)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed.timestamp()
    raise ToolError("I need a time like 2026-11-12T18:30 or '35 minutes'")


def set_reminder(ctx: ToolContext, text: str, when: str) -> str:
    text = (text or "").strip()
    if not text:
        raise ToolError("what should I remind you about?")
    due = _parse_when(when)
    if due < time.time() - 60:
        raise ToolError("that time is already in the past")
    reminder_id = ctx.memory.add_reminder(text, due)
    stamp = datetime.fromtimestamp(due).strftime("%a %d %b, %H:%M")
    return f"Reminder #{reminder_id} set for {stamp}: {text}"


def list_reminders(ctx: ToolContext) -> str:
    rows = ctx.memory.pending_reminders()
    if not rows:
        return "No reminders pending."
    return "\n".join(
        f"#{r['id']} {datetime.fromtimestamp(r['due_ts']).strftime('%a %d %b, %H:%M')} — {r['text']}"
        for r in rows
    )


def cancel_reminder(ctx: ToolContext, reminder_id: int) -> str:
    rows = {r["id"]: r for r in ctx.memory.pending_reminders()}
    if int(reminder_id) not in rows:
        return "No pending reminder with that number."
    ctx.memory.mark_reminder_fired(int(reminder_id))
    return f"Cancelled reminder #{reminder_id}."


def time_until(ctx: ToolContext, when: str) -> str:
    target = _parse_when(when)
    delta = target - time.time()
    if delta <= 0:
        return "That moment has already passed."
    bits = []
    for label, seconds in (("day", 86400), ("hour", 3600), ("minute", 60)):
        if delta >= seconds:
            amount = int(delta // seconds)
            bits.append(f"{amount} {label}{'s' if amount != 1 else ''}")
            delta -= amount * seconds
    return " and ".join(bits[:2]) or "less than a minute"


def register(registry: ToolRegistry) -> None:
    registry.add(
        "remember_fact",
        "Store something about the user permanently: their name, city, "
        "preferences, important people, recurring details. Also use it when the "
        "user says 'remember that…'.",
        {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "short label, e.g. home_city"},
                "value": {"type": "string"},
            },
            "required": ["key", "value"],
        },
        remember_fact,
        group="memory",
    )
    registry.add(
        "recall_facts",
        "Look up stored facts about the user.",
        {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "optional filter"}},
        },
        recall_facts,
        group="memory",
    )
    registry.add(
        "forget_fact",
        "Delete a stored fact the user no longer wants kept.",
        {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
        forget_fact,
        group="memory",
    )
    registry.add(
        "add_task",
        "Add an item to the user's to-do list.",
        {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
        add_task,
        group="productivity",
    )
    registry.add(
        "list_tasks",
        "Read back the user's to-do list.",
        {
            "type": "object",
            "properties": {"include_done": {"type": "boolean", "default": False}},
        },
        list_tasks,
        group="productivity",
    )
    registry.add(
        "complete_task",
        "Mark a to-do item as done, by id or by part of its title.",
        {
            "type": "object",
            "properties": {
                "task_id": {"type": "integer"},
                "title_match": {"type": "string"},
            },
        },
        complete_task,
        group="productivity",
    )
    registry.add(
        "set_reminder",
        "Set a reminder that SHACK will speak out loud when it is due. `when` must "
        "be an ISO timestamp (device local time, e.g. 2026-11-12T19:30) or a "
        "relative amount like '45 minutes'. Always resolve the date yourself with "
        "get_time first.",
        {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "what to remind about"},
                "when": {"type": "string"},
            },
            "required": ["text", "when"],
        },
        set_reminder,
        group="productivity",
    )
    registry.add(
        "list_reminders",
        "List pending reminders.",
        {"type": "object", "properties": {}},
        list_reminders,
        group="productivity",
    )
    registry.add(
        "cancel_reminder",
        "Cancel a pending reminder by its number.",
        {
            "type": "object",
            "properties": {"reminder_id": {"type": "integer"}},
            "required": ["reminder_id"],
        },
        cancel_reminder,
        group="productivity",
    )
    registry.add(
        "time_until",
        "How long until a given moment, in days/hours/minutes.",
        {
            "type": "object",
            "properties": {"when": {"type": "string"}},
            "required": ["when"],
        },
        time_until,
        group="time",
    )
