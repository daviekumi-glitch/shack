#!/data/data/com.termux/files/usr/bin/bash
# SHACK installer for Termux. Run: bash install.sh
set -e

echo "==> installing packages"
pkg update -y
pkg install -y python termux-api

echo "==> installing python dependencies"
pip install --upgrade pip
pip install -r requirements.txt

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo "==> created .env - put your Groq key in it:"
  echo "    nano .env   (set GROQ_KEY=gsk_...)"
fi

echo
echo "==> verifying"
python shack.py --check || true

echo
echo "Done. Start SHACK with:  python shack.py"
echo "Install the Termux:API app from F-Droid for voice, battery and clipboard tools."
