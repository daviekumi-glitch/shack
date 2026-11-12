# Legacy versions

The first steps of the project, kept for the record.

| file | what it did |
| --- | --- |
| `talk.py` | echoed whatever you typed |
| `talk2.py` | asked for your name once and remembered it in `memory.txt` |
| `talk3.py` | added jokes |
| `talk4.py` | first real version: Groq brain, free chat and 20 questions |
| `brain.py` | the original single-function Groq call used by `talk4.py` |

These still run (`python legacy/talk4.py` needs `GROQ_KEY` and `requests`), but
the maintained agent lives in the `shack/` package. Start it with `python shack.py`.
