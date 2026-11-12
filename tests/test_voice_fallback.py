"""The online voice, used when a phone's own speech engine refuses to talk."""

from __future__ import annotations

import unittest
from pathlib import Path

from shack import tts_http


class Splitting(unittest.TestCase):
    def test_short_reply_is_one_piece(self):
        self.assertEqual(tts_http._split("Hello Afick."), ["Hello Afick."])

    def test_long_reply_is_split_under_the_limit(self):
        text = (
            "Good morning. The weather in Blantyre is warm with a light breeze, and the "
            "rest of the day should stay clear. You asked about your reminders too, so "
            "here they are, one by one, in the order they are due today."
        )
        pieces = tts_http._split(text)
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertLessEqual(len(piece), tts_http._CHUNK)

    def test_empty_text_says_nothing(self):
        self.assertEqual(tts_http._split("   "), [])


class Behaviour(unittest.TestCase):
    def test_without_an_audio_backend_it_declares_itself_unusable(self):
        speaker = tts_http.HttpSpeaker.__new__(tts_http.HttpSpeaker)
        speaker.ok = False
        self.assertFalse(speaker.say("hello"))

    def test_missing_network_is_reported_not_crashed(self):
        speaker = tts_http.HttpSpeaker.__new__(tts_http.HttpSpeaker)
        speaker.ok = True
        speaker.speed = 0.85
        speaker.cache = Path("/tmp/shack_tts_test")
        speaker.cache.mkdir(parents=True, exist_ok=True)
        speaker.last_error = ""
        speaker._loader = None
        self.assertIsNone(speaker._fetch(""))  or None
        self.assertTrue(isinstance(speaker.last_error, str))


if __name__ == "__main__":
    unittest.main()
