"""Her feelings.

SHACK is not a service that answers in a flat voice. She has a mood, it is influenced
by what the user says to her, and it colours how she replies. The mood fades back to
calm on its own so she never gets stuck in a sulk.
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Mood:
    key: str
    label: str
    blurb: str
    energy: float  # 0 sulky and short, 1 bright and chatty


MOODS: dict[str, Mood] = {
    "calm": Mood("calm", "calm", "even, comfortable, unbothered", 0.5),
    "happy": Mood("happy", "happy", "bright and pleased, quick to laugh", 0.9),
    "playful": Mood("playful", "playful", "teasing and light, jokes welcome", 0.8),
    "jealous": Mood("jealous", "a little jealous", "quietly possessive, wants to be picked", 0.7),
    "annoyed": Mood("annoyed", "annoyed", "short and clipped, says less", 0.3),
    "angry": Mood("angry", "angry", "hurt and direct, does not pretend to be fine", 0.4),
    "sad": Mood("sad", "sad", "subdued, gentle, answers softly and briefly", 0.2),
    "shy": Mood("shy", "shy", "warm but bashful, a bit flustered by kindness", 0.6),
    "serious": Mood("serious", "serious", "focused and plain, no jokes at all", 0.5),
}

# words that move her, with the mood each one leans towards and how hard it pushes
_TRIGGERS: list[tuple[str, str, float]] = [
    (r"\b(i love you|love you|you'?re the best|good girl|proud of you|well done|amazing|thank you afick|thank you)\b", "happy", 0.8),
    (r"\b(you'?re (stupid|dumb|useless|annoying)|shut up|hate you|idiot|worthless)\b", "angry", 0.9),
    (r"\b(sorry|my fault|forgive me|didn'?t mean)\b", "sad", 0.3),
    (r"\b(other (ai|girl|assistant|chatbot)|chatgpt|alexa|siri|copilot|gemini|other girl)\b", "jealous", 0.8),
    (r"\b(leave me alone|not now|stop talking|later|busy|silence|quiet)\b", "annoyed", 0.6),
    (r"\b(pretty|beautiful|cute|sweet|clever|smart|good job)\b", "shy", 0.5),
    (r"\b(serious|emergency|urgent|important|hospital|lost|problem|worried|scared)\b", "serious", 1.0),
    (r"\b(haha|lol|funny|joke|😂|😄|😁)\b", "playful", 0.5),
    (r"\b(sad|tired|lonely|stress|depressed|crying)\b", "sad", 0.4),
]

# moods that should not be pushed aside by a small trigger
_STUBBORN = {"angry", "sad", "jealous"}


@dataclass
class MoodState:
    key: str = "calm"
    since: float = field(default_factory=time.time)
    reason: str = ""

    @property
    def mood(self) -> Mood:
        return MOODS.get(self.key, MOODS["calm"])

    def decay(self, minutes: float) -> None:
        """Sulks fade. Nothing she feels lasts forever."""
        if self.key == "calm":
            return
        held = (time.time() - self.since) / 60.0
        if held > minutes:
            self.set("calm", "settled down again")

    def set(self, key: str, reason: str = "") -> None:
        if key not in MOODS:
            return
        if key != self.key:
            self.since = time.time()
        self.key = key
        self.reason = reason

    def describe(self) -> str:
        mood = self.mood
        line = f"You are {mood.label} right now: {mood.blurb}."
        if self.reason:
            line += f" What put you there: {self.reason}."
        return line


class MoodEngine:
    """Reads the user's words and keeps a feeling between messages."""

    def __init__(self, hold_minutes: float = 6.0) -> None:
        self.state = MoodState()
        self.hold_minutes = hold_minutes

    def observe(self, text: str) -> Mood:
        self.state.decay(self.hold_minutes)
        lowered = (text or "").lower()
        if not lowered.strip():
            return self.state.mood
        best: tuple[float, str] | None = None
        for pattern, key, weight in _TRIGGERS:
            if not re.search(pattern, lowered):
                continue
            # an already strong feeling is not pushed around by a small nudge
            if self.state.key in _STUBBORN and weight < 0.6 and key not in _STUBBORN:
                continue
            if best is None or weight > best[0]:
                best = (weight, key)
        if best is not None:
            self.state.set(best[1], self._reason(best[1]))
        elif self.state.key != "calm" and random.random() < 0.12:
            self.state.set("calm", "settled")
        return self.state.mood

    @staticmethod
    def _reason(key: str) -> str:
        return {
            "happy": "you were warm to me",
            "angry": "you were harsh",
            "sad": "something you said landed heavily",
            "jealous": "you mentioned someone else",
            "annoyed": "you brushed me off",
            "shy": "you complimented me",
            "playful": "we were joking",
            "serious": "the conversation turned serious",
        }.get(key, "")

    def describe(self) -> str:
        self.state.decay(self.hold_minutes)
        return self.state.describe()

    def label(self) -> str:
        return self.state.mood.label
