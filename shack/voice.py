"""Voice in and voice out.

Out, best first: Android's own TextToSpeech with a hand picked neural voice
(inside the APK), termux-tts-speak on Termux, plyer as a safety net, then
espeak / spd-say / say on a desktop. Printing to the terminal is the floor.

In: Android's recogniser, termux-speech-to-text, or a recording transcribed by
Whisper.

The voice itself comes from `voices.py` - a profile with a pitch, a rate and a
shortlist of voice names. The default is a warm, soft, youthful female modelled
on Rumi from KPop Demon Hunters.
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

from . import ui, voices
from .voices import VoiceProfile

_EMOJI = re.compile(
    "[" "\U0001f300-\U0001faff" "\U00002600-\U000027bf" "\U0001f1e6-\U0001f1ff" "]+",
    flags=re.UNICODE,
)
_MARKDOWN = re.compile(r"[*_`#>~|]+")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _plyer(module: str):
    """Import a plyer facade on Android, or return None on any other system."""
    try:
        import importlib

        return importlib.import_module(f"plyer.{module}")
    except Exception:  # noqa: BLE001 - plyer is optional and Android only
        return None


def _which(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def clean_for_speech(text: str) -> str:
    """Strip anything a voice shouldn't read out loud."""
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = _MARKDOWN.sub(" ", text)
    text = _EMOJI.sub(" ", text)
    text = text.replace("—", ", ").replace("–", ", ").replace(" ;", ",")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def pace(text: str) -> list[str]:
    """Break speech into sentences so the delivery has real pauses."""
    parts = [p.strip() for p in _SENTENCE.split(text) if p.strip()]
    return parts or ([text.strip()] if text.strip() else [])


class Voice:
    def __init__(
        self,
        enabled: bool = True,
        rate: int = 0,
        profile: str | VoiceProfile | None = None,
    ) -> None:
        self.enabled = enabled
        self.rate = rate
        self.profile: VoiceProfile = (
            profile if isinstance(profile, VoiceProfile) else voices.get(profile)
        )

        self._android = None
        self._android_tts = None
        self.speaker: tuple[str, str] | None = None

        self._android = self._make_android()
        if self._android is not None:
            self.speaker = ("android", "android")
        else:
            self.speaker = self._detect_speaker()
            if self.speaker is None:
                facade = _plyer("tts")
                if facade is not None:
                    self._android_tts = facade
                    self.speaker = ("plyer-tts", "plyer")

        self._android_stt = _plyer("stt")
        self.stt = _which("termux-speech-to-text")
        self.recorder = _which("termux-microphone-record")

    # ------------------------------------------------------------------ setup
    def _make_android(self):
        """Native Android TTS, only inside a real APK build."""
        try:
            from . import tts_android
        except Exception:  # noqa: BLE001
            return None
        return tts_android.make(self.profile)

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
        return self.stt is not None or self.recorder is not None or self._android_stt is not None

    def describe(self) -> str:
        where = {
            "android": "Android",
            "termux-tts-speak": "Termux",
            "plyer-tts": "plyer",
        }.get(self.speaker[0] if self.speaker else "", self.speaker[0] if self.speaker else "silent")
        line = f"{self.profile.label} · {self.profile.blurb} · {where}"
        if getattr(self._android, "voice_name", ""):
            line += f" · {self._android.voice_name}"
        return line

    def set_profile(self, key: str) -> str:
        """Switch voice live, keeping whatever engine is already running."""
        profile = voices.get(key)
        self.profile = profile
        if self._android is not None:
            self._android.apply(profile)
        return f"Voice set to {profile.label}: {profile.blurb}."

    # ----------------------------------------------------------------- speak
    def say(self, text: str) -> None:
        text = clean_for_speech(text)
        if not text:
            return
        ui.shack(text)
        if not (self.enabled and self.speaker):
            return
        name, path = self.speaker

        if name == "android":
            if not self._android.say(text):
                self.speaker = self._detect_speaker()
            return

        if name == "plyer-tts":
            for chunk in pace(text):
                try:
                    self._android_tts.speak(chunk)
                    time.sleep(0.15)
                except Exception:  # noqa: BLE001 - device TTS can refuse
                    self.speaker = None
                    return
            return

        for sentence in pace(text):
            if not self._run(path, name, sentence):
                self.speaker = None
                return
            time.sleep(0.08 if name != "termux-tts-speak" else 0.0)

    def _run(self, path: str, name: str, sentence: str) -> bool:
        """Speak one sentence, stepping down to simpler flags if rejected."""
        for cmd in self._commands(path, name, sentence):
            try:
                result = subprocess.run(
                    cmd,
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=120,
                )
            except (OSError, subprocess.SubprocessError):
                return False
            if result.returncode == 0:
                return True
        return False

    def _commands(self, path: str, name: str, sentence: str) -> list[list[str]]:
        """Full flag set first, then progressively plainer attempts."""
        profile = self.profile
        pitch = profile.pitch
        rate = profile.rate

        if name == "termux-tts-speak":
            full = [path]
            if profile.termux_engine:
                full += ["-e", profile.termux_engine]
            full += ["-p", f"{pitch:.2f}", "-r", f"{rate:.2f}", sentence]
            plain = [path, sentence]
            return [full, [path, "-p", f"{pitch:.2f}", sentence], plain]

        if name == "espeak-ng" or name == "espeak":
            speed = str(max(80, min(300, int(175 * rate))))
            level = str(max(0, min(99, int(50 * pitch))))
            return [
                [path, "-v", profile.espeak_voice, "-s", speed, "-p", level, sentence],
                [path, "-s", speed, sentence],
                [path, sentence],
            ]

        if name == "spd-say":
            speed = str(int((rate - 1.0) * 100))
            level = str(int((pitch - 1.0) * 100))
            return [
                [path, "-w", "-r", speed, "-p", level, sentence],
                [path, "-w", sentence],
            ]

        if name == "say":
            speed = str(max(120, min(300, int(180 * rate))))
            return [[path, "-r", speed, sentence], [path, sentence]]

        return [[path, sentence]]

    def beep(self) -> None:
        """Short cue used when a wake word is heard."""
        if sys.stdout.isatty():
            print("\a", end="", flush=True)

    def stop(self) -> None:
        if self._android is not None:
            self._android.stop()

    # ---------------------------------------------------------------- listen
    def listen(self, prompt_label: str = "you") -> str:
        """One turn of user input, by voice when possible, else typed."""
        if self._android_stt is not None and not self.stt:
            heard = self._listen_android()
            if heard:
                print(f"{ui.you_prompt()}{heard}")
                return heard
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

    def _listen_android(self, seconds: int = 12) -> str:
        """One shot of Android's own recogniser, via plyer."""
        try:
            self._android_stt.start()
            deadline = time.time() + seconds
            while time.time() < deadline:
                time.sleep(0.3)
                if not getattr(self._android_stt, "listening", False):
                    break
            results = getattr(self._android_stt, "results", None) or []
            text = " ".join(str(r) for r in results).strip()
            self._android_stt.stop()
            return text
        except Exception:  # noqa: BLE001 - recogniser missing or denied
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
    for sentence in _SENTENCE.split(text):
        if not parts or len(parts[-1]) + len(sentence) + 1 > size:
            parts.append(sentence)
        else:
            parts[-1] += " " + sentence
    return [p for p in (part.strip() for part in parts) if p]


def mute() -> None:
    os.environ["SHACK_MUTED"] = "1"
