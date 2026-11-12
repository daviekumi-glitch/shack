#!/usr/bin/env bash
# Install the Android toolchain needed to turn SHACK into an APK.
# Safe to re-run: anything already present is skipped.
#
#   bash tools/setup_android.sh
#
# Afterwards:  buildozer android debug
set -euo pipefail

SDK="${ANDROIDSDK:-/opt/android-sdk}"
NDK_VERSION="${ANDROIDNDK_VERSION:-25.1.8937393}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-34.0.0}"
PLATFORM="${ANDROID_PLATFORM:-android-34}"

echo "==> system packages"
if command -v apt-get >/dev/null; then
  # this sandbox reaches the internet on 443 only, so force https mirrors
  if [ -f /etc/apt/sources.list.d/debian.sources ]; then
    sed -i 's|URIs: http://|URIs: https://|g' /etc/apt/sources.list.d/debian.sources
  fi
  DEBIAN_FRONTEND=noninteractive apt-get update -qq || true
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    openjdk-17-jdk-headless unzip zip autoconf automake libtool pkg-config cmake \
    libffi-dev libssl-dev zlib1g-dev patch build-essential libncurses-dev \
    libltdl-dev ccache >/dev/null
fi

echo "==> python build tools"
python3 -m pip install -q --upgrade buildozer cython

echo "==> android sdk"
mkdir -p "$SDK/cmdline-tools"
if [ ! -x "$SDK/cmdline-tools/latest/bin/sdkmanager" ]; then
  curl -sL -o /tmp/cmdline-tools.zip \
    https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
  unzip -q -o /tmp/cmdline-tools.zip -d "$SDK/cmdline-tools"
  rm -rf "$SDK/cmdline-tools/latest"
  mv "$SDK/cmdline-tools/cmdline-tools" "$SDK/cmdline-tools/latest"
fi

export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"
yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
"$SDKMANAGER" --sdk_root="$SDK" "platform-tools" "build-tools;$BUILD_TOOLS" \
  "platforms;$PLATFORM" "ndk;$NDK_VERSION"

echo
echo "toolchain ready in $SDK (ndk $NDK_VERSION)"
