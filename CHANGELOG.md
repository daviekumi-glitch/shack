# Changelog

Every change, in plain language. Newest first.

## 2.1.7 - sound that proves itself, and better manners

*Sound.* A voice can be listed by Android, be selectable, and still make no noise when
its speech data was never downloaded. Guessing was not enough, so now she tests. At
startup she walks down a ranked list of voices, silently speaks one syllable into each,
and watches for Android's "speech started" callback. The first voice that answers is
kept. If the engine has not been proven yet when you ask her something, she proves it
first, then talks. The engine is also given fifteen seconds to start instead of five,
because Google's engine is slow on a cold phone and used to give up silently.

*Manners.* She used to answer "Afick made you" when asked who created her, which is
the wrong person. She now answers in the first person about herself: "Afick made me."

*No key to type.* Builds can now carry a working key, baked in at build time from a
private value that never enters the repository. A fresh install then works the moment
it opens, and /key still overrides it. Without that value baked in, the app asks for a
key exactly as before.

## 2.1.6 - she knows you, remembers you, and a new way in

*Her creator.* She now knows Afick built her, and says so if anyone asks. The fact
is stored the first time she runs, so it survives everything.

*Loading.* Two new screens in her colours. Android shows a pink and purple splash
while the app starts, then the app itself opens on a violet loading screen with her
orb breathing and a ring rippling out of it, "waking up" underneath, before the chat
appears.

*Deep memory.* She learns from what you say without being asked. Her name, your
name, your birthday, where you live, what you do, what you like and dislike, the
people in your life, and anything after "remember" all go into a database on the
phone. They survive closing the app and clearing the conversation. Before each
reply she recalls the facts that matter for that question, so asking about your
sister brings up her name rather than a random list. New /remember and /memories
commands let you add and inspect what she knows.

*Her face is the orb, always.* The violet orb you gave me is now her face in three
places: the loading screen, the small avatar beside her name, and the big orb on the
home screen. All three breathe, and two rings push out from the big one. While she
speaks the rings ripple faster in time with her words, while she listens they swell
slowly, and at rest they drift.

*The microphone.* Tapping the new microphone icon listens for ten seconds with a
visible countdown, then switches itself off, and the icon glows pink while it is on.
The Voice button is now a sound wave icon.

## 2.1.5 - she can be heard, and she can hear you

Two real faults, found by reading the phone code.

*Silence.* She was choosing Google's neural voice, which only works over the
network. With weak or missing data that voice plays nothing at all, so the screen
animated while the phone stayed quiet. Now she checks whether the phone is online
before picking that voice and falls back to a voice stored on the device, so she
talks with or without data. Her speech is also routed to the media stream at full
volume, which some phones need before they will play a word.

*The microphone.* Android's recogniser returns up to a thousand candidate
sentences, and the app was joining all of them into one long nonsense sentence
before sending it to the model. It now uses the best sentence only. It also asked
for offline recognition by default, which fails silently when the offline language
pack was never downloaded, so it now asks for online recognition. The microphone
permission is requested and, if refused, you get the exact Settings path to fix it.
Every recogniser error is now a plain sentence: no data, blocked microphone, heard
nothing, or recogniser busy.

*New /sound command.* It reports the speech engine, the chosen voice, whether that
voice needs data, the media volume level, and says a test line out loud.

## 2.1.4 - the new look

The whole screen is redesigned after the Aura reference you sent, with SHACK in place of the name.

* Deep violet night background with soft, rounded glass-style panels.
* Header: a lilac sparkle logo, "SHACK" in pink, and Voice and Mic on the right.
* The orb is now a permanent centrepiece at the top, no longer scrolling away. Under
  it the status reads "SHACK Ready / How can I help you today?" and changes to
  Thinking, Listening or Speaking as she works.
* Chat bubbles: yours on the right, hers on the left with a small sparkle beside
  them. Short messages get short bubbles; long ones wrap.
* A pill-shaped "Ask anything..." bar with a sparkle as the send button.
* The orb animation from 2.1.3 carries over: it swells and flickers while she
  speaks, slowly swells while she listens, and breathes at rest.

## 2.1.3 - Rumi stays, and her face moves

* Rumi is now permanent. Tapping Voice no longer cycles her to Nova or anything
  else; the button just says hello in her current voice. Only /voice can change it,
  and every restart brings Rumi back.
* Her face moves while she talks: the orb in the header and the big orb on the home
  screen pulse in time with each spoken line, dip while she is thinking, and swell
  slowly while she is listening.
* Speech length is estimated from the word count and her speaking rate, so the
  movement lasts as long as the sentence does and then settles back to breathing.

## 2.1.2 - tell me why the brain is unreachable

* The app now shows the actual reason a request failed in the chat, instead of a
  generic "check the network or the API key".
* New `/test` command checks the key and the connection to Groq and says plainly
  what is wrong: bad key, no data connection, or a model missing from the account.
* Keys are cleaned before saving, so a stray space or newline from a phone
  clipboard no longer breaks them, and anything that does not start with `gsk_`
  is refused with a clear message.
* Errors from the agent now reach the screen instead of only the console.

## 2.1.1 - her face, and an APK that actually builds

### A face

New glowing violet orb: launcher icon, header avatar, and a larger breathing copy that greets you on the home screen until you send your first message.

### The APK builds now

Three separate build failures, all fixed:

setuptools crash: python-for-android's bundled setuptools 51 died while byte-compiling (byte_compile() got an unexpected keyword argument 'dry_run'). recipes/setuptools/ overrides that recipe with an empty one, since the app does not need setuptools at runtime.

Artifact keys broke buildozer: android.debug_artifact and android.release_artifact were passed to the toolchain as a command (invalid choice: 'shack-2.1.1-debug'). Removed; buildozer names the file itself.

Stale half-built kivy produced missing .c errors. A clean kivy build resolves it.

Toolchain pinned to python-for-android v2024.01.21 (Python 3.11) and NDK 25b.

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
