#!/usr/bin/env python3
"""SHACK launcher.

    python shack.py              talk to SHACK
    python shack.py --check      verify setup, key, tools and voice
    python shack.py --wake       wait for the wake word, hands free
"""

import sys

from shack.cli import main

if __name__ == "__main__":
    sys.exit(main())
