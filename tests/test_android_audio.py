"""Voice choice and microphone handling, tested without a phone.

These cover the two faults that made SHACK silent and deaf in 2.1.4:
a network voice being chosen with no data, and the recogniser's thousand
candidate sentences being joined into nonsense.
"""

from __future__ import annotations

import unittest

from shack import voices
from shack.tts_android import AndroidSpeaker
from shack.voice import Voice


class FakeLocale:
    def __init__(self, language="en", country="US", rtl=False):
        self._language, self._country, self._rtl = language, country, rtl

    def getLanguage(self):
        return self._language

    def getCountry(self):
        return self._country

    def isRtl(self):
        return self._rtl


class FakeVoice:
    def __init__(self, name, network=False, quality=400, language="en", country="US"):
        self._name, self._network, self._quality = name, network, quality
        self._locale = FakeLocale(language, country)

    def getName(self):
        return self._name

    def isNetworkConnectionRequired(self):
        return self._network

    def getQuality(self):
        return self._quality

    def getLocale(self):
        return self._locale


def speaker_for(profile=None):
    """An AndroidSpeaker with no Android behind it, just for scoring."""
    speaker = AndroidSpeaker.__new__(AndroidSpeaker)
    speaker.profile = profile or voices.RUMI
    return speaker


class VoiceChoice(unittest.TestCase):
    def test_network_voice_wins_when_online(self):
        speaker = speaker_for()
        neural = FakeVoice("en-us-x-sfg-network", network=True, quality=500)
        local = FakeVoice("en-us-x-sfg-local", network=False, quality=400)
        self.assertGreater(
            speaker._score(neural, network_up=True), speaker._score(local, network_up=True)
        )

    def test_local_voice_wins_when_offline(self):
        speaker = speaker_for()
        neural = FakeVoice("en-us-x-sfg-network", network=True, quality=500)
        local = FakeVoice("en-us-x-sfg-local", network=False, quality=400)
        self.assertGreater(
            speaker._score(neural, network_up=False), 0
        )
        self.assertGreater(
            speaker._score(local, network_up=False), speaker._score(neural, network_up=False)
        )

    def test_other_languages_are_refused(self):
        speaker = speaker_for()
        self.assertEqual(speaker._score(FakeVoice("de-DE-x", language="de", country="DE")), 0.0)

    def test_diagnose_mentions_silent_causes(self):
        speaker = speaker_for()
        speaker.ok = False
        speaker.voice_name = ""
        speaker.needs_network_voice = True
        speaker.network_ok = False
        speaker.last_error = "the phone's speech engine would not start"
        speaker.media_volume = lambda: (0, 15)
        report = speaker.diagnose()
        self.assertIn("NOT ready", report)
        self.assertIn("MUTED", report)
        self.assertIn("no data", report)


class FakeSTT:
    def __init__(self, results=None, errors=None):
        self._results = list(results or [])
        self._errors = list(errors or [])
        self.results, self.errors, self.partial_results = [], [], []
        self.prefer_offline = True
        self.language = None
        self.polls = 0

    @property
    def listening(self):
        self.polls += 1
        if self.polls >= 2:
            self.results = list(self._results)
            self.errors = list(self._errors)
            return False
        return True

    def start(self):
        self.results, self.errors, self.polls = [], [], 0

    def stop(self):
        pass


def voice_with(stt, permission="granted"):
    voice = Voice.__new__(Voice)
    voice.recorder = None
    voice.stt = None
    voice._android = None
    voice.listen_error = ""
    voice._android_stt = stt
    voice.mic_permission = lambda: permission
    return voice


class Microphone(unittest.TestCase):
    def test_only_the_best_sentence_is_used(self):
        voice = voice_with(FakeSTT(results=["what is the weather", "watt is the whether"]))
        self.assertEqual(voice._listen_android(), "what is the weather")

    def test_online_recognition_is_requested(self):
        stt = FakeSTT(results=["hello"])
        voice_with(stt)._listen_android()
        self.assertFalse(stt.prefer_offline)
        self.assertEqual(stt.language, "en-US")

    def test_blocked_microphone_is_explained(self):
        voice = voice_with(FakeSTT(results=["hello"]), permission="denied")
        self.assertEqual(voice._listen_android(), "")
        self.assertIn("blocked", voice.listen_error)

    def test_recogniser_errors_become_words(self):
        voice = voice_with(FakeSTT(errors=["error:network"]))
        self.assertEqual(voice._listen_android(), "")
        self.assertIn("data connection", voice.listen_error)

    def test_unknown_error_keeps_the_code(self):
        voice = voice_with(FakeSTT(errors=["error:weird"]))
        voice._listen_android()
        self.assertIn("weird", voice.listen_error)


if __name__ == "__main__":
    unittest.main()
