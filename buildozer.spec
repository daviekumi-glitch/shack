[app]

# The APK that comes out of this file is the SHACK Android app:
#   buildozer android debug
# The toolchain is installed by tools/setup_android.sh.

title = SHACK
package.name = shack
package.domain = org.shack

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,txt,env
source.exclude_dirs = tests,legacy,bin,.git,.github,.buildozer,__pycache__,shack.egg-info
source.exclude_patterns = .env,*.db,*.db-journal

version = 2.1.4

# requests pulls in urllib3, chardet and idna itself, but p4a wants them named.
requirements = python3,kivy,requests,urllib3,certifi,idna,charset-normalizer,plyer

icon.filename = %(source.dir)s/assets/icon.png

orientation = portrait
fullscreen = 0

android.permissions = INTERNET,RECORD_AUDIO,VIBRATE,POST_NOTIFICATIONS
android.api = 31
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

# Toolchain location. tools/setup_android.sh installs exactly this.
android.sdk_path = /opt/android-sdk
android.ndk_path = /opt/android-sdk/ndk/25.1.8937393

# The app has no launcher icon set per density; Kivy scales the one above.

# Python for Android. v2024.01.21 ships Python 3.11, which is the newest
# release where requests and its dependencies have ready built wheels. The
# current master builds Python 3.14 and fails on those wheels.
p4a.branch = v2024.01.21
p4a.local_recipes = %(source.dir)s/recipes

[buildozer]

log_level = 2
warn_on_root = 0
