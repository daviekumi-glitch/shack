"""Device and system tools. Termux commands are used when present."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone

from .registry import ToolContext, ToolError, ToolRegistry


def termux(cmd: list[str], timeout: int = 15) -> str:
    """Run a termux-api helper, returning stdout ('' if unavailable)."""
    if not shutil.which(cmd[0]):
        raise ToolError(
            f"{cmd[0]} is not installed. On Termux run: pkg install termux-api "
            "and install the Termux:API app."
        )
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ToolError(f"{cmd[0]} failed: {exc.__class__.__name__}") from exc
    return (out.stdout or "").strip()


def termux_json(cmd: list[str], timeout: int = 15) -> dict:
    raw = termux(cmd, timeout=timeout)
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ToolError(f"{cmd[0]} returned something unexpected") from exc


# --------------------------------------------------------------------- time
def get_time(ctx: ToolContext, what: str = "both") -> str:
    now = datetime.now().astimezone()
    what = (what or "both").lower()
    stamp = now.strftime("%A %d %B %Y, %H:%M")
    if what == "date":
        return now.strftime("%A %d %B %Y")
    if what == "time":
        return now.strftime("%H:%M")
    return f"{stamp} ({now.tzname() or 'local time'})"


def date_math(ctx: ToolContext, days: int = 0) -> str:
    from datetime import timedelta

    target = datetime.now().astimezone() + timedelta(days=int(days))
    return target.strftime("%A %d %B %Y")


# ------------------------------------------------------------------- device
def device_status(ctx: ToolContext) -> str:
    facts: list[str] = []
    try:
        battery = termux_json(["termux-battery-status"])
        pct = battery.get("percentage")
        plug = battery.get("plugged", "UNPLUGGED")
        temp = battery.get("temperature")
        line = f"battery {pct}%"
        if plug and plug != "UNPLUGGED":
            line += " (charging)"
        if temp:
            line += f", {temp}°C"
        facts.append(line)
    except ToolError as exc:
        facts.append(f"battery: {exc}")

    try:
        wifi = termux_json(["termux-wifi-connectioninfo"])
        if wifi.get("ssid"):
            facts.append(f"wifi '{wifi['ssid']}' at {wifi.get('link_speed_mbps', '?')} Mbps")
    except ToolError:
        pass

    try:
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        facts.append(f"{free_gb:.1f} GB free storage")
    except OSError:
        pass

    facts.append(f"clock says {datetime.now().astimezone().strftime('%H:%M')}")
    return "; ".join(facts)


def clipboard_read(ctx: ToolContext) -> str:
    text = termux(["termux-clipboard-get"])
    return text or "(clipboard is empty)"


def clipboard_write(ctx: ToolContext, text: str) -> str:
    termux(["termux-clipboard-set", text])
    return "Copied to the clipboard."


def vibrate(ctx: ToolContext, milliseconds: int = 400) -> str:
    termux(["termux-vibrate", "-d", str(int(milliseconds)), "-f"])
    return "Vibrated."


def torch(ctx: ToolContext, state: str = "toggle") -> str:
    state = (state or "toggle").lower()
    if state not in {"on", "off", "toggle"}:
        raise ToolError("state must be on, off or toggle")
    termux(["termux-torch", state])
    return f"Torch {state}."


def set_volume(ctx: ToolContext, stream: str = "music", level: int = 50) -> str:
    stream = (stream or "music").lower()
    if stream not in {"music", "call", "ring", "alarm", "notification", "system"}:
        raise ToolError("unknown audio stream")
    level = max(0, min(100, int(level)))
    termux(["termux-volume", stream, str(level)])
    return f"{stream} volume set to {level}%."


def open_url(ctx: ToolContext, url: str) -> str:
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url.lstrip("/")
    termux(["termux-open-url", url])
    return f"Opened {url} on the device."


def notify(ctx: ToolContext, title: str = "SHACK", body: str = "") -> str:
    args = ["termux-notification", "--title", title]
    if body:
        args += ["--content", body]
    termux(args)
    return "Notification posted."


def speech_to_text_device(ctx: ToolContext) -> str:
    text = termux(["termux-speech-to-text"], timeout=40)
    return text or "(heard nothing)"


def register(registry: ToolRegistry) -> None:
    registry.add(
        "get_time",
        "Current local date and/or time on the device. Use it whenever the user "
        "asks about now, today, deadlines or elapsed time.",
        {
            "type": "object",
            "properties": {
                "what": {
                    "type": "string",
                    "enum": ["time", "date", "both"],
                    "description": "Which part to return (default both).",
                }
            },
        },
        get_time,
        group="time",
    )
    registry.add(
        "date_math",
        "Work out which calendar date it is N days from today (negative for the past).",
        {
            "type": "object",
            "properties": {"days": {"type": "integer", "description": "Day offset"}},
            "required": ["days"],
        },
        date_math,
        group="time",
    )
    registry.add(
        "device_status",
        "Battery level, charging state, wifi name, free storage and the clock. "
        "Use for questions about the phone itself.",
        {"type": "object", "properties": {}},
        device_status,
        group="device",
    )
    registry.add(
        "clipboard_read",
        "Read the phone's clipboard.",
        {"type": "object", "properties": {}},
        clipboard_read,
        group="device",
    )
    registry.add(
        "clipboard_write",
        "Put text on the phone's clipboard so the user can paste it elsewhere.",
        {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        clipboard_write,
        group="device",
    )
    registry.add(
        "vibrate",
        "Make the phone vibrate briefly, e.g. to get the user's attention.",
        {
            "type": "object",
            "properties": {"milliseconds": {"type": "integer", "default": 400}},
        },
        vibrate,
        group="device",
    )
    registry.add(
        "torch",
        "Turn the phone torch on, off, or toggle it.",
        {
            "type": "object",
            "properties": {"state": {"type": "string", "enum": ["on", "off", "toggle"]}},
        },
        torch,
        group="device",
    )
    registry.add(
        "set_volume",
        "Change a phone volume stream between 0 and 100.",
        {
            "type": "object",
            "properties": {
                "stream": {
                    "type": "string",
                    "enum": ["music", "call", "ring", "alarm", "notification", "system"],
                },
                "level": {"type": "integer", "minimum": 0, "maximum": 100},
            },
            "required": ["level"],
        },
        set_volume,
        group="device",
    )
    registry.add(
        "open_url",
        "Open a web page in the phone's browser.",
        {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        open_url,
        group="device",
    )
    registry.add(
        "notify",
        "Post an Android notification the user can see later.",
        {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "body": {"type": "string"},
            },
        },
        notify,
        group="device",
    )
