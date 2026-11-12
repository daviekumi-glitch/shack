"""Guarded shell access, the way a real assistant reaches the machine."""

from __future__ import annotations

import re
import subprocess

from .registry import ToolContext, ToolError, ToolRegistry

BLOCKED = [
    r"\brm\s+-[a-z]*[rf]", r"\bmkfs\b", r"\bdd\s+if=", r"\bshutdown\b", r"\breboot\b",
    r":\(\)\s*\{", r"\bchmod\s+-R\s+777\s+/", r">\s*/dev/(?!null)", r"\bfdisk\b",
    r"\bwipe\b", r"\buserdel\b", r"\bpasswd\b", r"\bsudo\b", r"\bsu\b",
    r"curl[^|]*\|\s*(ba)?sh",
]


def run_shell(ctx: ToolContext, command: str, timeout: int = 25) -> str:
    command = (command or "").strip()
    if not command:
        raise ToolError("no command given")
    if getattr(ctx.config, "safe_mode", True):
        for pattern in BLOCKED:
            if re.search(pattern, command):
                raise ToolError(
                    "that command looks destructive, so safe mode refuses it. "
                    "Set SHACK_SAFE_MODE=false in .env if you really need it."
                )
    if ctx.confirm and not ctx.confirm(f"Run shell command: {command}"):
        return "The user declined to run that command."
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=max(1, min(120, int(timeout))),
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolError(f"command timed out after {timeout}s") from exc
    except OSError as exc:
        raise ToolError(f"could not run the command: {exc}") from exc

    out = ((proc.stdout or "") + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")).strip()
    if not out:
        out = "(no output)"
    if len(out) > 3500:
        out = out[:3500] + "\n… (truncated)"
    return f"exit {proc.returncode}\n{out}"


def register(registry: ToolRegistry) -> None:
    registry.add(
        "run_shell",
        "Run a shell command on the device (Termux). Use for system information, "
        "file listing, package management, and anything the other tools cannot do. "
        "Destructive commands are blocked in safe mode and the user is always asked "
        "before it runs.",
        {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout": {"type": "integer", "default": 25},
            },
            "required": ["command"],
        },
        run_shell,
        risky=True,
        group="shell",
    )
