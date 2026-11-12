"""Voice in and voice out.

Out: termux-tts-speak on Android, espeak/spd-say/say elsewhere, print as the
last resort. In: termux-speech-to-text, or a recording transcribed by Whisper
when voice input is enabled.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import ui

_EMOJI = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]+",
    flags=re.UNICODE,
)
_MARKDOWN = re.compile(r"[*_`#>~|]+")


def _which(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def clean_for_speech(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = _MARKDOWN.sub(" ", text)
    text = _EMOJI.sub(" ", text)
    text = text.replace("—", ", ").replace("–", ", ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


class Voice:
    def __init__(self, enabled: bool = True, rate: int = 0) -> None:
        self.enabled = enabled
        self.rate = rate
        self.speaker = self._detect_speaker()
        self.stt = _which("termux-speech-to-text")
        self.recorder = _which("termux-microphone-record")

    @staticmethod
    def _detect_speaker() -> tuple[str, str] | None:
        for name in ("termux-tts-speak", "espeak-ng", "espeak", "spd-say", "say"):
            path = _which(name)
            if path:
                return (name, path)
        return None

    @property
    def can_speak(self) -> bool:
        return self.speaker is not None

    @property
    def can_listen(self) -> bool:
        return self.stt is not None or self.recorder is not None

    # ----------------------------------------------------------------- speak
    def say(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text:
            return
        ui.shack(text)
        if not (self.enabled and self.speaker):
            return
        name, path = self.speaker
        for chunk in _chunks(text, 360):
            try:
                if name == "termux-tts-speak":
                    cmd = [path, "-r", str(self.rate or 160), chunk]
                elif name == "spd-say":
                    cmd = [path, "-w", chunk]
                elif name == "say":
                    cmd = [path, chunk]
                else:  # espeak / espeak-ng
                    cmd = [path, "-s", str(self.rate or 165), chunk]
                subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
            except (OSError, subprocess.SubprocessError):
                self.speaker = None
                return

    def beep(self) -> None:
        """Short cue used when a wake word is heard."""
        if sys.stdout.isatty():
            print("\a", end="", flush=True)

    # ---------------------------------------------------------------- listen
    def listen(self, prompt_label: str = "you") -> str:
        """One turn of user input, by voice when possible, else typed."""
        if self.stt:
            ui.info("listening…")
            try:
                out = subprocess.run(
                    [self.stt],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                text = (out.stdout or "").strip()
                if text:
                    print(f"{ui.you_prompt()}{text}")
                    return text
                ui.warn("nothing heard, type instead")
            except (OSError, subprocess.SubprocessError):
                ui.warn("speech recognition failed, type instead")
        try:
            return input(ui.you_prompt()).strip()
        except EOFError:
            return ""

    def record_and_transcribe(self, brain, seconds: int = 6) -> str:
        """Record a clip with termux-microphone-record and transcribe it."""
        if not self.recorder:
            ui.warn("termux-microphone-record not found (pkg install termux-api)")
            return ""
        tmp = Path(tempfile.mkdtemp()) / "clip.m4a"
        try:
            subprocess.run(
                [self.recorder, "-f", str(tmp), "-l", str(seconds)],
                check=False,
                timeout=seconds + 10,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.4)
            if not tmp.exists() or tmp.stat().st_size < 512:
                ui.warn("no audio captured")
                return ""
            return brain.transcribe(tmp)
        except (OSError, subprocess.SubprocessError) as exc:
            ui.warn(f"recording failed: {exc.__class__.__name__}")
            return ""
        finally:
            try:
                subprocess.run(
                    [self.recorder, "-q"],
                    check=False,
                    timeout=10,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except (OSError, subprocess.SubprocessError):
                pass
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass


def _chunks(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    parts: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if not parts or len(parts[-1]) + len(sentence) + 1 > size:
            parts.append(sentence)
        else:
            parts[-1] += " " + sentence
    return [p for p in (part.strip() for part in parts) if p]


def mute() -> None:
    os.environ["SHACK_MUTED"] = "1"
