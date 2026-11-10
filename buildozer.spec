[app]
title = Device Health
package.name = devicehealth
package.domain = org.safety
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = server, mock, Children_Data, .git, .github, bin, .buildozer, __pycache__
source.exclude_patterns = *.db, *.apk, *.zip, server.py, mock_main.py, *.log
version = 1.0.0

# Dependencies
requirements = python3,kivy==2.3.0,requests,urllib3,charset-normalizer,idna,plyer,pyjnius

# Stable python-for-android branch (Python 3.11)
p4a.branch = v2024.01.21

# Android Permissions
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,ACCESS_BACKGROUND_LOCATION,CAMERA,RECORD_AUDIO,READ_PHONE_STATE,WAKE_LOCK,RECEIVE_BOOT_COMPLETED,REQUEST_IGNORE_BATTERY_OPTIMIZATIONS,POST_NOTIFICATIONS,FOREGROUND_SERVICE

# API levels
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a

# Foreground / Auto-start
android.wakelock = True
android.entrypoint = org.kivy.android.PythonActivity

[buildozer]
log_level = 2
warn_on_root = 1
