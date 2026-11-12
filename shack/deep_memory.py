"""Long term memory: what she learns about you and how she recalls it.

Two jobs live here.

*Learning.* Every message you send is scanned for things worth keeping: your
name, your birthday, where you live, what you do, what you like and dislike, the
people in your life, and anything you say after "remember". Those become facts in
the database, so they survive closing the app, and they survive clearing the
conversation.

*Recalling.* Facts are not all equal at every moment. Before each reply the facts
are scored against what you just asked and the best ones are put back into her
prompt, so a question about your sister brings up her name instead of a random
list of everything stored.
"""

from __future__ import annotations

import re
import time
import unicodedata

# Always worth recalling, whatever the question.
ALWAYS = ("user_name", "creator", "birthday", "location", "job")

_WORDS = re.compile(r"[a-z0-9']+")
_STOP = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "to", "of", "in", "on", "at", "for", "with", "about", "from", "by", "as", "it",
    "this", "that", "these", "those", "i", "you", "he", "she", "we", "they", "me",
    "my", "your", "his", "her", "our", "their", "do", "does", "did", "can", "could",
    "what", "who", "when", "where", "why", "how", "please", "shack", "tell", "know",
}


def _tokens(text: str) -> set[str]:
    text = unicodedata.normalize("NFKD", (text or "").lower())
    return {w for w in _WORDS.findall(text) if len(w) > 2 and w not in _STOP}


# ---------------------------------------------------------------- learning
# Ordered: the first pattern that matches wins for a given key.
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("user_name", r"\b(?:my name is|my name's|call me|i am called|i'm called)\s+([A-Za-z][\w'-]{1,24})"),
    ("birthday", r"\bmy birthday is\s+([^.!?\n]{2,40})"),
    ("birthday", r"\bi was born (?:on|in)\s+([^.!?\n]{2,40})"),
    ("location", r"\bi (?:live|stay) in\s+([^.!?\n]{2,40})"),
    ("location", r"\bi(?:'m| am) from\s+([^.!?\n]{2,40})"),
    ("job", r"\bi work as (?:an?\s+)?([^.!?\n]{2,40})"),
    ("job", r"\bi(?:'m| am) (?:an?\s+)?([a-z]+(?:\s+[a-z]+)?)\s+by profession\b"),
    ("job", r"\bi study\s+([^.!?\n]{2,40})"),
    ("age", r"\bi(?:'m| am)\s+(\d{1,2})\s+years old"),
    ("likes", r"\bi (?:really )?(?:like|love|enjoy)\s+([^.!?\n]{2,60})"),
    ("dislikes", r"\bi (?:really )?(?:hate|dislike|can't stand|cannot stand)\s+([^.!?\n]{2,60})"),
    ("people", r"\bmy (sister|brother|mother|mom|mum|father|dad|wife|husband|girlfriend|boyfriend|friend|son|daughter|boss)\s+(?:is called|is named|is)\s+([A-Z][\w'-]{1,24})"),
    ("phone", r"\bmy (?:number|phone number) is\s+([+\d][\d\s-]{6,18})"),
    ("email", r"\bmy email is\s+([^\s,]{5,60}@[^\s,]{3,40})"),
    ("goal", r"\bmy goal is\s+([^.!?\n]{3,80})"),
)

_REMEMBER = re.compile(r"\b(?:remember|don't forget|do not forget)\b[:\s]*(?:that\s+)?(.{3,180})", re.I)


def extract_facts(text: str) -> list[tuple[str, str]]:
    """Pull lasting facts out of one message. Never raises, never invents."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    body = (text or "").strip()
    if not body:
        return found

    for match in _REMEMBER.finditer(body):
        note = match.group(1).strip(" .!?")
        if note and "remember" not in seen:
            found.append(("note", note))
            seen.add("remember")

    for key, pattern in _PATTERNS:
        if key in seen:
            continue
        match = re.search(pattern, body, re.I)
        if not match:
            continue
        if key == "people":
            relation = match.group(1).lower()
            person = " ".join(part.capitalize() for part in match.group(2).split())
            found.append((f"person_{relation}", person))
            seen.add(key)
            continue
        value = match.group(1).strip(" .,!?'\"")
        if key == "user_name" or key.startswith("person_"):
            value = " ".join(part.capitalize() for part in value.split())
        if value and len(value) < 120:
            found.append((key, value))
            seen.add(key)
    return found


# -------------------------------------------------------------- recalling
def score(fact_key: str, fact_value: str, query_tokens: set[str]) -> float:
    """How relevant one stored fact is to the current question."""
    if fact_key in ALWAYS:
        return 100.0
    haystack = _tokens(fact_key.replace("_", " ") + " " + fact_value)
    if not haystack or not query_tokens:
        return 0.0
    overlap = len(haystack & query_tokens)
    if not overlap:
        return 0.0
    return overlap / max(3, len(haystack)) * 10 + overlap


def recall(facts: list[tuple[str, str]], query: str, limit: int = 12) -> list[tuple[str, str]]:
    """The facts worth putting in front of her for this message."""
    query_tokens = _tokens(query)
    scored = []
    for key, value in facts:
        weight = score(key, value, query_tokens)
        if weight > 0:
            scored.append((weight, key, value))
    scored.sort(key=lambda row: (-row[0], row[1]))
    chosen = [(key, value) for _, key, value in scored[:limit]]
    if not chosen:
        # nothing matched: still give her the durable essentials
        chosen = [(k, v) for k, v in facts if k in ALWAYS][:limit]
    return chosen


def summarise_for_prompt(facts: list[tuple[str, str]]) -> str:
    """A compact block of memory, deduplicated and readable."""
    if not facts:
        return "nothing stored yet"
    lines = []
    seen = set()
    for key, value in facts:
        line = f"{key.replace('_', ' ')}: {value}"
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return "\n".join(f"- {line}" for line in lines[:24])


def stamp() -> int:
    return int(time.time())
