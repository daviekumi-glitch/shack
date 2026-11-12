"""Android text to speech, driven directly through pyjnius.

plyer can only say text with whatever voice the phone happens to have selected.
Talking to TextToSpeech ourselves lets SHACK pick the voice: a neural (network)
English female where one is installed, then set pitch and rate on top. That
selection is what makes the APK sound like a person instead of a satnav.

Every call is defensive. If anything at all goes wrong the caller falls back to
plyer, then to printing.
"""

from __future__ import annotations

import socket
import time

from .voices import VoiceProfile

_CHUNK = 360

# Android constants we need by hand so this module never dies on a missing class.
STREAM_MUSIC = 3
USAGE_MEDIA = 1
CONTENT_TYPE_SPEECH = 1


def _log(msg: str) -> None:
    try:
        from . import ui

        ui.info(msg)
    except Exception:  # noqa: BLE001 - never break speech over a log line
        pass


class AndroidSpeaker:
    """Wraps android.speech.tts.TextToSpeech with voice selection."""

    def __init__(self, profile: VoiceProfile) -> None:
        self.profile = profile
        self.ok = False
        self.voice_name = ""
        self.voice_quality = 0
        self._tts = None
        self._ready = False
        self.network_ok = True
        self.needs_network_voice = False
        self.last_error = ""
        self._init()

    # ------------------------------------------------------------------ setup
    @staticmethod
    def network_up(timeout: float = 3.0) -> bool:
        """A network voice is silent without data, so ask before choosing one."""
        for host in ("api.groq.com", "8.8.8.8"):
            try:
                socket.create_connection((host, 443), timeout=timeout).close()
                return True
            except OSError:
                continue
        return False

    def _init(self) -> None:
        try:
            from jnius import PythonJavaClass, autoclass, cast, java_method
        except Exception:  # noqa: BLE001 - not an Android runtime
            return

        speaker = self

        class _Listener(PythonJavaClass):
            __javainterfaces__ = ["android/speech/tts/TextToSpeech$OnInitListener"]
            __javacontext__ = "app"

            @java_method("(I)V")
            def onInit(self, status: int) -> None:
                speaker._ready = status == 0

        try:
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            context = cast("android.content.Context", activity)
            tts_class = autoclass("android.speech.tts.TextToSpeech")
            self._listener = _Listener()
            self._tts = tts_class(context, self._listener)
        except Exception:  # noqa: BLE001
            self._tts = None
            return

        deadline = time.time() + 5
        while time.time() < deadline and not self._ready:
            time.sleep(0.1)
        if not self._ready or self._tts is None:
            return

        try:
            self._route_to_speaker()
            self._apply_voice()
            self._tts.setPitch(float(self.profile.pitch))
            self._tts.setSpeechRate(float(self.profile.rate))
            self.ok = True
        except Exception:  # noqa: BLE001
            self.ok = False

    def _route_to_speaker(self) -> None:
        """Without this some phones play her into nothing at all."""
        try:
            from jnius import autoclass, cast

            builder = autoclass("android.media.AudioAttributes$Builder")()
            builder.setUsage(USAGE_MEDIA)
            builder.setContentType(CONTENT_TYPE_SPEECH)
            attributes = builder.build()
            self._tts.setAudioAttributes(cast("android.media.AudioAttributes", attributes))
        except Exception:  # noqa: BLE001 - old Android, keep going
            pass

    def media_volume(self) -> tuple[int, int]:
        """How loud the media stream is, so we can tell you why she is silent."""
        try:
            from jnius import autoclass, cast

            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            context = cast("android.content.Context", activity)
            manager = autoclass("android.media.AudioManager")
            audio = context.getSystemService(context.AUDIO_SERVICE)
            return (
                int(audio.getStreamVolume(manager.STREAM_MUSIC)),
                int(audio.getStreamMaxVolume(manager.STREAM_MUSIC)),
            )
        except Exception:  # noqa: BLE001
            return (-1, -1)

    def _apply_voice(self) -> None:
        """Choose the most human sounding English voice the device has."""
        try:
            voices = list(self._tts.getVoices() or [])
        except Exception:  # noqa: BLE001
            return
        if not voices:
            return

        online = self.network_up()
        self.network_ok = online
        best = None
        best_score = -1.0
        for voice in voices:
            score = self._score(voice, online)
            if score > best_score:
                best, best_score = voice, score
        if best is None or best_score <= 0:
            return
        try:
            self._tts.setVoice(best)
            self.voice_name = str(best.getName())
            self.voice_quality = int(best.getQuality())
            self.needs_network_voice = bool(best.isNetworkConnectionRequired())
        except Exception:  # noqa: BLE001
            return

    def _score(self, voice, network_up: bool = True) -> float:
        try:
            name = str(voice.getName()).lower()
            locale = voice.getLocale()
            language = str(locale.getLanguage()).lower()
            country = str(locale.getCountry()).upper()
            quality = int(voice.getQuality())
            network = bool(voice.isNetworkConnectionRequired())
        except Exception:  # noqa: BLE001
            return 0.0

        if language != "en" or bool(voice.getLocale().isRtl()):
            return 0.0

        score = 1.0
        if network:
            # Google's neural voices live here, but they are silent without data,
            # so they only win when the phone really is online.
            score += 50.0 if network_up else -20.0
        score += min(quality, 500) / 20.0
        if country in {"US", "GB"}:
            score += 8.0
        for place, hint in enumerate(self.profile.android_hints):
            if hint in name:
                score += 120.0 - place * 10.0
                break
        # the profile hints are ordered best first, keep that ordering intact
        return score

    # ------------------------------------------------------------------ speak
    def say(self, text: str) -> bool:
        self.last_error = ""
        if not self.ok or self._tts is None:
            self.last_error = "the phone's speech engine would not start"
            return False
        try:
            from jnius import autoclass

            text_to_speech = autoclass("android.speech.tts.TextToSpeech")
            Bundle = autoclass("android.os.Bundle")
            params = Bundle()
            params.putInt(text_to_speech.Engine.KEY_PARAM_STREAM, STREAM_MUSIC)
            params.putFloat(text_to_speech.Engine.KEY_PARAM_VOLUME, 1.0)
            for index, chunk in enumerate(_chunks(text, _CHUNK)):
                queue = text_to_speech.QUEUE_FLUSH if index == 0 else text_to_speech.QUEUE_ADD
                self._tts.speak(
                    chunk, queue, params, f"shack-{int(time.time() * 1000)}-{index}"
                )
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = f"speaking failed ({exc.__class__.__name__})"
            return False

    def diagnose(self) -> str:
        """One line a person can act on."""
        parts = ["engine " + ("ready" if self.ok else "NOT ready")]
        if self.voice_name:
            parts.append("voice " + self.voice_name)
        if self.needs_network_voice:
            parts.append("network voice" + ("" if self.network_ok else ", and there is no data"))
        volume, top = self.media_volume()
        if volume >= 0:
            parts.append(f"media volume {volume} of {top}" + (" (MUTED)" if volume == 0 else ""))
        if self.last_error:
            parts.append(self.last_error)
        return ", ".join(parts)

    def apply(self, profile: VoiceProfile) -> None:
        self.profile = profile
        if not self.ok or self._tts is None:
            return
        try:
            self._tts.setPitch(float(profile.pitch))
            self._tts.setSpeechRate(float(profile.rate))
            self._apply_voice()
        except Exception:  # noqa: BLE001
            return

    def stop(self) -> None:
        try:
            if self._tts is not None:
                self._tts.stop()
        except Exception:  # noqa: BLE001
            return

    def shutdown(self) -> None:
        try:
            if self._tts is not None:
                self._tts.stop()
                self._tts.shutdown()
        except Exception:  # noqa: BLE001
            return
        self._tts = None
        self.ok = False


def make(profile: VoiceProfile) -> AndroidSpeaker | None:
    """Return a working speaker, or None when this isn't an Android app."""
    try:
        speaker = AndroidSpeaker(profile)
    except Exception:  # noqa: BLE001
        return None
    return speaker if speaker.ok else None


def _chunks(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out: list[str] = []
    for sentence in text.replace("\n", " ").split(". "):
        candidate = sentence.strip()
        if not candidate:
            continue
        if out and len(out[-1]) + len(candidate) + 2 <= size:
            out[-1] = f"{out[-1]}. {candidate}"
        else:
            out.append(candidate)
    return out or [text[:size]]
