[app]
title = Device Health
package.name = devicehealth
package.domain = org.safety
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
source.exclude_dirs = server, mock, Children_Data, .git, .github, bin, .buildozer, __pycache__, Captured_Photos
source.exclude_patterns = *.db, *.apk, *.zip, server.py, mock_main.py, *.log, database.py, client_mobile.py, colab_builder.py, colab_run_all.py, gen_colab.py
version = 1.0.0

# Minimal pure requirements - zero third-party pip dependencies
requirements = python3,kivy==2.3.0,pyjnius

p4a.branch = master

# Android Permissions
android.permissions = INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,CAMERA,RECORD_AUDIO,READ_PHONE_STATE,WAKE_LOCK,FOREGROUND_SERVICE

# Android API Target
android.api = 33
android.minapi = 21
android.ndk = 25b
android.archs = arm64-v8a
android.accept_sdk_license = True

# Screen and Service
orientation = portrait
android.wakelock = True
android.entrypoint = org.kivy.android.PythonActivity

[buildozer]
log_level = 2
warn_on_root = 1
