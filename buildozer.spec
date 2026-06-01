[app]
title = Visual Assist
package.name = visualassist
package.domain = org.visualassist
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,cfg,weights,names
version = 0.1.0

requirements = python3,kivy==2.3.0,pyjnius,numpy,opencv-python-headless

orientation = user
fullscreen = 0

# Android
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.allow_backup = True

android.permissions = INTERNET,FOREGROUND_SERVICE,FOREGROUND_SERVICE_MEDIA_PROJECTION,SYSTEM_ALERT_WINDOW,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,POST_NOTIFICATIONS,WAKE_LOCK

# Foreground service (Pyjnius will instantiate org.visualassist.app.ServiceVisualassist)
services = Visualassist:service.py:foreground

# اختياري: شعار ولون
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png

[buildozer]
log_level = 2
warn_on_root = 0
