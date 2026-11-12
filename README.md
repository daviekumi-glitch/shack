# SHACK

A personal AI agent that lives on your Android phone.

Talk to it out loud, ask it things, and it actually does them: checks your battery,
searches the web, reads a page for you, does the maths, remembers what matters to
you, keeps your to-dos and reminders, and speaks the answer back. Runs in Termux,
uses Groq for the brain, and needs nothing but a free API key.

```
you  › hey shack, what's the weather and do I need to charge my phone?
     ↳ get_weather   {"location": "Blantyre"}
     ↳ device_status
SHACK › It's clear and 28 degrees in Blantyre today, and you're at 43 percent, so yes, charge soon.
```

## What it can do

* **Talk.** Speech out through `termux-tts-speak`, speech in through the microphone,
  or plain typing if you'd rather.
* **Think with tools.** The model decides which capability to call. It doesn't
  invent answers when a tool can find the real one.
* **Remember.** Conversations, personal facts, to-dos and reminders persist in a
  local SQLite database and survive restarts.
* **Act on the phone.** Battery and storage, clipboard, torch, volume, vibration,
  notifications, opening links, and the microphone.
* **Reach the web.** Live search, page reading, and weather with no API keys.
* **Run commands.** Shell access, with safe mode refusing anything destructive and
  a yes/no check before every command.
* **Speak up when it's due.** Reminders fire while SHACK is running and say the
  reminder out loud.

## Install (Termux)

```bash
pkg update && pkg install python termux-api
git clone https://github.com/daviekumi-glitch/shack.git
cd shack
pip install -r requirements.txt
cp .env.example .env
nano .env          # set GROQ_KEY from https://console.groq.com/keys
python shack.py --check
```

`install.sh` does the first steps for you: `bash install.sh`.

Install the **Termux:API** app from F-Droid as well, otherwise the device tools
(battery, clipboard, torch, speech input) have nothing to talk to.

## Use it

```bash
python shack.py                 # talk, typed or spoken
python shack.py --listen        # microphone on
python shack.py --wake          # hands free: waits for "hey shack"
python shack.py --no-voice      # silent, text only
python shack.py --check         # verify key, storage, tools, voice
python shack.py --model openai/gpt-oss-20b
```

In a session:

```
/help              command list
/tools             every capability, grouped
/facts             what it remembers about you
/remember home_city = Blantyre
/forget home_city
/tasks             open to-dos
/reminders         pending reminders
/voice on|off      speak replies or stay quiet
/listen on|off     microphone on or off
/model [name]      show or change the model
/reset             clear this conversation, keep facts and tasks
/exit
```

## The tools

| group | tools |
| --- | --- |
| time | `get_time` `date_math` `time_until` |
| device | `device_status` `clipboard_read` `clipboard_write` `torch` `vibrate` `set_volume` `open_url` `notify` |
| web | `web_search` `fetch_url` `get_weather` |
| utility | `calculate` `convert_units` `text_stats` |
| memory | `remember_fact` `recall_facts` `forget_fact` |
| productivity | `add_task` `list_tasks` `complete_task` `set_reminder` `list_reminders` `cancel_reminder` |
| shell | `run_shell` |

Adding one is about fifteen lines: write the function in `shack/tools/`, then
register it with a name, a description and a JSON schema. The model picks it up
automatically.

## The voice

SHACK ships with five voices. The default is *Rumi*: young, warm, soft and in no
hurry, modelled on the character from KPop Demon Hunters.

```
/voice             what is speaking right now
/voice rumi        switch to the warm default
/voice orion       low, steady male
/voice off         silence, keep the text
/voices            list every profile
```

In the APK, the *Voice* button cycles through them and says a sample, so you can
pick by ear in a couple of taps.

How a phone voice is chosen, in order:

1. Android's own TextToSpeech, driven through pyjnius, so SHACK can pick a specific
   voice instead of accepting the phone's default.
2. Every installed English voice is scored: network (neural) voices first, then
   audio quality, then the profile's own shortlist, then US/GB preference.
3. Pitch and rate are applied on top (Rumi is 1.06 pitch, 0.94 rate).
4. `plyer.tts`, then espeak, then text only, if any of that is missing.

The biggest quality jump comes from Google's neural voices: in Android settings,
open *Text-to-speech output*, choose *Speech Services by Google*, then install the
*English* voice data and enable network voices. A profile cannot make a 1990s
engine sound like a person.

Sentences are spoken one at a time with a short gap, which is most of the reason it
sounds conversational rather than read out.

## Configuration

Everything lives in `.env` (see `.env.example`).

| variable | default | meaning |
| --- | --- | --- |
| `GROQ_KEY` | — | required, from console.groq.com |
| `SHACK_MODEL` | `openai/gpt-oss-20b` | any Groq chat model |
| `SHACK_VOICE_OUT` | `true` | speak replies |
| `SHACK_VOICE_IN` | `false` | start with the mic on |
| `SHACK_VOICE` | `rumi` | voice profile: rumi, nova, sage, orion, system |
| `SHACK_WAKE_WORD` | `hey shack` | phrase used by `--wake` |
| `SHACK_SAFE_MODE` | `true` | block destructive shell commands |
| `SHACK_DATA_DIR` | `~/.shack` | database and logs |

## The Android app

The APK is the same agent with a touch interface: chat bubbles, a text box, and
Send, Mic and Voice buttons.

Build it yourself:

```bash
bash tools/setup_android.sh      # JDK, Android SDK, build tools, NDK
buildozer android debug          # produces bin/shack-2.1.0-debug.apk
```

Install on the phone: copy the APK across, tap it, allow installs from this source.
On first launch it asks for your Groq key, keeps it in the app's private storage,
and remembers it.

What works inside the app: chat, all 26 tools that don't need Termux, Android text
to speech with voice selection, Android speech recognition, reminders while the app
is open, and full memory. What needs Termux: shell commands, clipboard, torch,
volume, opening links, and Whisper transcription.

## How it's built

```
main.py               Android app entry point (Kivy)
buildozer.spec        APK recipe
shack.py              launcher
shack/
  cli.py              flags, greeting, commands, self check
  agent.py            the loop: prompt, history, tool calls, speech
  brain.py            Groq client, retries, tool calling, Whisper
  memory.py           SQLite: messages, facts, tasks, reminders
  voice.py            text to speech, speech to text, recording
  voices.py           the five voice profiles
  tts_android.py      Android TextToSpeech with real voice selection
  config.py           .env loading and settings
  ui.py               terminal output
  tools/              one module per capability group
tools/setup_android.sh  installs the APK build toolchain
tests/                offline tests, no key needed
legacy/               the original talk.py to talk4.py steps
```

One turn looks like this: your words go into memory, the system prompt is rebuilt
with your name, stored facts, open tasks, pending reminders and a summary of older
conversation, the model answers either with words or with tool calls, tools run one
at a time until it has what it needs, and the final answer is stored and spoken.

Long conversations get compacted: older messages are summarised into one paragraph
of memory and trimmed away, so the agent keeps its context without dragging the
whole transcript to every request.

## Safety

* Safe mode refuses `rm -rf`, `mkfs`, `dd`, shutdown, credential changes and
  pipe-to-shell downloads.
* Every shell command asks you first.
* Memory is local. Nothing but the conversation, the tool results and recorded audio
  goes to Groq.

## Troubleshooting

**No API key** — `GROQ_KEY` is empty in `.env`, or you ran the app from a different
folder. `python shack.py --check` names the missing piece.

**Model not found** — set `SHACK_MODEL=llama-3.3-70b-versatile` or another model your
key can use.

**No sound** — install Termux:API, and check `termux-tts-speak "test"` works on its
own. On other systems SHACK falls back to `espeak-ng`, `spd-say` or `say`.

**Search returns nothing** — the phone is offline, or a search engine is throttling
requests. SHACK tries Bing, then DuckDuckGo twice.

**Reminders don't fire** — they only speak while SHACK is running.

## Roadmap

* Wake word that listens with a real model instead of the system recogniser
* Calendar and contacts through Termux:API
* A tiny web control panel
* Voice interruption, so you can cut SHACK off mid-sentence

Built with Python, Groq and Termux. No framework, no server, no account.
