"""Voice personalities.

Each profile is a small bundle of settings: how high the voice sits, how fast it
talks, which Android voice to look for, and which engine to ask for. The default
is modelled on Rumi from KPop Demon Hunters: young, warm, soft, slightly breathy,
and in no hurry.

These are the knobs a phone can actually give us. Pitch and rate do most of the
work, and picking a neural (network) Android voice is what stops it sounding
like a 1990s satnav.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VoiceProfile:
    key: str
    label: str
    blurb: str
    pitch: float
    rate: float
    android_hints: tuple[str, ...]
    termux_engine: str
    espeak_voice: str

    def summary(self) -> str:
        return f"{self.label} ({self.blurb})"


# Warm, youthful female with a little air in it. The hints are ordered: the
# first Android voice whose name contains one of them wins.
RUMI = VoiceProfile(
    key="rumi",
    label="Rumi",
    blurb="warm, soft, youthful female, unhurried",
    pitch=1.06,
    rate=0.94,
    android_hints=(
        "en-us-x-sfg#female",
        "en-us-x-iol",
        "en-gb-x-gba#female",
        "#female_1",
        "female",
    ),
    termux_engine="com.google.android.tts",
    espeak_voice="en+f3",
)

NOVA = VoiceProfile(
    key="nova",
    label="Nova",
    blurb="bright, quick, upbeat female",
    pitch=1.14,
    rate=1.04,
    android_hints=("en-us-x-tpf", "en-us-x-iom", "#female_2", "female"),
    termux_engine="com.google.android.tts",
    espeak_voice="en+f4",
)

SAGE = VoiceProfile(
    key="sage",
    label="Sage",
    blurb="calm, level, measured",
    pitch=1.0,
    rate=0.92,
    android_hints=("en-gb-x-rjs", "en-us-x-iob", "female"),
    termux_engine="com.google.android.tts",
    espeak_voice="en+f2",
)

ORION = VoiceProfile(
    key="orion",
    label="Orion",
    blurb="low, steady male",
    pitch=0.86,
    rate=0.96,
    android_hints=("en-us-x-sfg#male", "#male_1", "male"),
    termux_engine="com.google.android.tts",
    espeak_voice="en+m3",
)

SYSTEM = VoiceProfile(
    key="system",
    label="System",
    blurb="whatever the phone uses by default",
    pitch=1.0,
    rate=1.0,
    android_hints=(),
    termux_engine="",
    espeak_voice="en",
)

PROFILES: dict[str, VoiceProfile] = {
    p.key: p for p in (RUMI, NOVA, SAGE, ORION, SYSTEM)
}
DEFAULT_PROFILE = RUMI.key


def get(name: str | None) -> VoiceProfile:
    """Look a profile up, falling back to the default rather than failing."""
    if not name:
        return PROFILES[DEFAULT_PROFILE]
    key = name.strip().lower()
    return PROFILES.get(key, PROFILES[DEFAULT_PROFILE])


def names() -> list[str]:
    return list(PROFILES)


def describe_all() -> str:
    return "\n".join(
        f"/voice {p.key:<7} {p.label:<7} {p.blurb}" for p in PROFILES.values()
    )
