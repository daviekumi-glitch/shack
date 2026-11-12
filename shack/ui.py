"""Small terminal UI helpers (no third-party dependencies)."""

from __future__ import annotations

import os
import sys

_COLOR = os.environ.get("NO_COLOR") is None and sys.stdout.isatty()

_ANSI = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "red": "\033[31m",
    "magenta": "\033[35m",
    "blue": "\033[34m",
}


def tint(text: str, color: str) -> str:
    if not _COLOR:
        return text
    return f"{_ANSI.get(color, '')}{text}{_ANSI['reset']}"


def banner(model: str, voice: bool) -> None:
    line = "─" * 46
    print(tint(line, "dim"))
    print(tint("  SHACK", "bold") + tint("  ·  personal AI agent", "dim"))
    print(tint(f"  brain: {model}   voice: {'on' if voice else 'off'}", "dim"))
    print(tint(line, "dim"))
    print(tint("  /help for commands   /exit to stop", "dim"))
    print()


def shack(text: str) -> None:
    print(tint("SHACK", "cyan") + tint(" › ", "dim") + text)


def you_prompt() -> str:
    return tint("you", "green") + tint(" › ", "dim")


def info(text: str) -> None:
    print(tint(f"· {text}", "dim"))


def tool(label: str, detail: str = "") -> None:
    body = f"↳ {label}"
    if detail:
        body += f" {tint(detail, 'dim')}"
    print(tint(body, "magenta"))


def warn(text: str) -> None:
    print(tint(f"! {text}", "yellow"))


def error(text: str) -> None:
    print(tint(f"✗ {text}", "red"))


def ask(text: str) -> str:
    try:
        return input(tint(f"? {text} ", "yellow")).strip()
    except EOFError:
        return ""
