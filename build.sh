#!/usr/bin/env bash
# Build the Android APK. The speech engine query lives in buildozer.spec through
# android.extra_manifest_xml, so nothing has to be patched by hand.
set -euo pipefail
cd "$(dirname "$0")"
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
exec buildozer android debug "$@"
