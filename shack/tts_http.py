"""A voice that does not need the phone's speech engine to be healthy.

Some Android builds refuse to start a text to speech engine for an installed app,
and when that happens every mention of a voice is silent no matter how it is
configured. This module is the way around it: the sentence is fetched as a small
audio file from a public voice endpoint and played through Kivy's own audio player,
which the app already ships.

It costs a fraction of a second of network per sentence, so it is only used when
the on-device engine cannot speak.
"""

from __future__ import annotations

import hashlib
import time
import urllib.parse
import urllib.request
from pathlib import Path

_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; SM-A125F) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
_ENDPOINT = "https://translate.google.com/translate_tts"
_CHUNK = 170  # the endpoint rejects longer queries


def _split(text: str, limit: int = _CHUNK) -> list[str]:
    """Break a reply into pieces the endpoint accepts, on sentence boundaries."""
    text = " ".join((text or "").split())
    if not text:
        return []
    pieces, current = [], ""
    for sentence in text.replace("!", ".").replace("?", ".").split("."):
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current} {sentence}.".strip()
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            pieces.append(current)
        while len(sentence) > limit:
            cut = sentence.rfind(" ", 0, limit)
            cut = cut if cut > 40 else limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        current = sentence
    if current:
        pieces.append(current)
    return [p for p in pieces if p.strip()]


class HttpSpeaker:
    """Speaks by downloading audio and playing it with Kivy."""

    def __init__(self, cache_dir: Path, speed: float = 0.85) -> None:
        self.ok = False
        self.last_error = ""
        self.voice_name = "online voice"
        self.needs_network_voice = True
        self.speed = speed
        self._sound = None
        self._player = None
        try:
            from kivy.core.audio import SoundLoader

            self._loader = SoundLoader
            self.cache = Path(cache_dir)
            self.cache.mkdir(parents=True, exist_ok=True)
            self.ok = True
        except Exception as exc:  # noqa: BLE001 - no audio backend in this build
            self.last_error = f"no audio player available ({exc.__class__.__name__})"

    # ------------------------------------------------------------------ audio
    def _fetch(self, sentence: str) -> Path | None:
        digest = hashlib.sha1(
            f"{self.speed}:{sentence}".encode("utf-8", "ignore")
        ).hexdigest()[:16]
        target = self.cache / f"say_{digest}.mp3"
        if target.exists() and target.stat().st_size > 800:
            return target
        query = urllib.parse.urlencode(
            {
                "ie": "UTF-8",
                "client": "tw-ob",
                "tl": "en",
                "ttsspeed": f"{self.speed}",
                "q": sentence,
            }
        )
        request = urllib.request.Request(
            f"{_ENDPOINT}?{query}",
            headers={
                "User-Agent": _USER_AGENT,
                "Referer": "https://translate.google.com/",
                "Accept": "*/*",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                audio = response.read()
        except Exception as exc:  # noqa: BLE001 - offline or refused
            self.last_error = f"the online voice could not be downloaded ({exc.__class__.__name__})"
            return None
        if len(audio) < 800:
            self.last_error = "the online voice returned no audio"
            return None
        try:
            target.write_bytes(audio)
        except OSError:
            return None
        return target

    def _play_media_player(self, path: Path) -> bool:
        """Android's own media player. A different subsystem from the speech engine."""
        try:
            from jnius import autoclass

            MediaPlayer = autoclass("android.media.MediaPlayer")
            player = MediaPlayer()
            player.setDataSource(str(path))
            player.prepare()
            seconds = player.getDuration() / 1000.0
            player.start()
            self._player = player
            limit = time.time() + min(max(seconds, 1.0) + 1.0, 30.0)
            while time.time() < limit and player.isPlaying():
                time.sleep(0.05)
            player.stop()
            player.release()
            self._player = None
            return True
        except Exception as exc:  # noqa: BLE001 - fall through to Kivy
            self.last_error = f"the media player refused it ({exc.__class__.__name__})"
            return False

    def _play_kivy(self, path: Path) -> bool:
        try:
            sound = self._loader.load(str(path))
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"the audio file would not play ({exc.__class__.__name__})"
            return False
        if sound is None:
            self.last_error = "the audio file would not play"
            return False
        self._sound = sound
        sound.play()
        limit = time.time() + min(max(getattr(sound, "length", 3.0) or 3.0, 1.0), 25.0)
        while time.time() < limit and getattr(sound, "state", "") == "play":
            time.sleep(0.05)
        return True

    def say(self, text: str) -> bool:
        if not self.ok:
            return False
        sentences = _split(text)
        if not sentences:
            return True
        for sentence in sentences:
            path = self._fetch(sentence)
            if path is None:
                return False
            if self._play_media_player(path):
                continue
            if not self._play_kivy(path):
                return False
        return True

    def stop(self) -> None:
        player = getattr(self, "_player", None)
        if player is not None:
            try:
                player.stop()
                player.release()
            except Exception:  # noqa: BLE001
                pass
            self._player = None
        if self._sound is not None:
            try:
                self._sound.stop()
            except Exception:  # noqa: BLE001
                pass


def make(cache_dir: Path, speed: float = 0.85) -> HttpSpeaker | None:
    speaker = HttpSpeaker(cache_dir, speed=speed)
    return speaker if speaker.ok else None
