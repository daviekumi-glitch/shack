# Changelog

Every change, in plain language. Newest first.

## 2.1.0 - a voice you want to talk to

### Voice profiles

* `shack/voices.py` - named voices, each a pitch, a rate, a shortlist of Android
  voice names and an engine. Five to start: Rumi (default), Nova, Sage, Orion and
  System.
* Rumi is the default: young, warm, soft, unhurried. Pitch 1.06, rate 0.94, so it
  sits a little high and takes its time instead of rattling through the answer.
* `/voice` shows what is speaking, `/voice rumi` switches, `/voice off` goes silent,
  and `/voices` lists every profile. In the app, the *Voice* button cycles them and
  speaks a sample so you can hear the change immediately.
* `SHACK_VOICE` sets the voice without touching any code.

### Android text to speech, done properly

* `shack/tts_android.py` - talks to `android.speech.tts.TextToSpeech` through
  pyjnius. It scores every installed English voice and picks the most human one:
  network (neural) voices first, then quality, then the profile's own hints, then
  preference for US/GB.
* Pitch and rate are applied to the chosen voice, not just to the default one.
* plyer stays as the fallback if pyjnius is unavailable, so the app still speaks.

### Speech that sounds spoken

* Sentences are now spoken one at a time with a short gap, instead of one flat
  block. That single change removes most of the robotic feel.
* Em dashes, semicolons and markdown are turned into commas before speaking.
* Termux's rate flag was wrong: it used to pass 160 (words per minute) where
  `termux-tts-speak` wants a multiplier around 1.0, which made it talk at double
  speed. It now passes the profile's own rate.
* Every backend gets a fallback ladder: full flags first, then a simpler command,
  then bare text. An engine that rejects a flag no longer goes silent.

## 2.0.0 - the release that runs on a phone

### Android app

* `main.py` - the Kivy front end: chat bubbles, text box, Send, Mic and Voice
  buttons. Same agent, same tools, same memory as the terminal.
* `buildozer.spec` - the recipe that turns this repository into an installable APK.
* `assets/icon.png` - launcher icon.
* `tools/setup_android.sh` - installs JDK, Android SDK, build tools and NDK, and
  fixes apt to use https mirrors.
* First run asks for a Groq key and keeps it in the app's private storage.

### Voice that works inside an APK

* Android speech recognition through `plyer.stt`, one shot per Mic tap.
* Device tools degrade instead of crashing: battery, vibrate and notifications fall
  back to Android APIs when Termux:API is missing.
* Termux-only tools that have no Android equivalent fail with one readable sentence
  instead of a traceback.

### Memory that cannot fail to load

* `shack/simple_memory.py` - a JSON backed store with the same methods as the SQLite
  one, for Android Python builds without `sqlite3`.
* `create_memory()` picks SQLite when it works, JSON when it doesn't.

### Bug fixes

* Deadlock in `older_messages()`: it re-read a row count while holding the same lock,
  so the first attempt at compacting a long conversation froze the app. The lock is
  reentrant now and a regression test covers it.
* Fixed artifact names that used an unsupported `%(arch)s` placeholder and made
  buildozer refuse to read its own spec.
* Transcription sends the right audio MIME type for the file it uploads.
* `ToolRegistry.remove()` added so `--no-shell` stops reaching into private state.
* `ShackAgent.stopped` property added instead of reading a private flag.
* Unused imports removed; `pyflakes` is clean.

## 2.0.0 - the agent rewrite

### Structure

* Split the script into a package: `cli`, `agent`, `brain`, `memory`, `voice`,
  `config`, `ui`, and a `tools` folder with one module per capability group.
* `shack.py` stays as the launcher.
* Old versions moved to `legacy/`.

### A real agent loop

* The model calls tools, several times per turn, until it has an answer. Six rounds
  maximum, then it says so instead of spinning.
* 26 capabilities: clock and dates, web search, page reading, weather, maths, unit
  conversion, text stats, device state, clipboard, torch, volume, vibration,
  notifications, opening links, facts, tasks, reminders and shell.
* Risky tools ask before running.

### Memory

* SQLite store for conversation history, permanent facts, to-dos and reminders.
* Long conversations are summarised into a rolling note and trimmed.
* Facts, open tasks and pending reminders are injected into the system prompt.

### Interface

* Speech in through the microphone, or typing when there is no recogniser.
* Wake word mode (`--wake`) for hands free use.
* Reminders speak out loud through a background watcher.
* Commands: `/help`, `/tools`, `/facts`, `/remember`, `/forget`, `/tasks`,
  `/reminders`, `/reset`, `/voice`, `/voices`, `/listen`, `/model`, `/session`,
  `/exit`.
* `--check` self test for the key, storage, tools, voice and model.
* A readable error for every failure that used to crash.

### Tooling and docs

* `requirements.txt`, `.env.example`, `.gitignore`, `install.sh`.
* Offline tests covering the registry, the rules that guard risky tools, memory,
  tasks, reminders, history trimming, the deadlock and the voice profiles.
* A README with install, usage, configuration, architecture, safety and
  troubleshooting.

## 1.4 - the original scripts

* `talk.py` echoed what you typed.
* `talk2.py` asked for your name and kept it in `memory.txt`.
* `talk3.py` added jokes.
* `talk4.py` gave it a Groq brain, free chat and a game of twenty questions.
