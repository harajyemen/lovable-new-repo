[app]
title = Visual Assist
package.name = visualassist
package.domain = org.visualassist

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,onnx,pb
version = 1.0.0

requirements = python3==3.11.9,kivy==2.3.1,pyjnius,plyer,numpy,opencv

orientation = portrait
fullscreen = 0

# Android
android.api = 33
android.minapi = 24
android.ndk_api = 24
android.archs = arm64-v8a
android.accept_sdk_license = True
android.permissions = INTERNET, FOREGROUND_SERVICE, POST_NOTIFICATIONS, SYSTEM_ALERT_WINDOW, WAKE_LOCK, FOREGROUND_SERVICE_MEDIA_PROJECTION, RECORD_AUDIO, READ_MEDIA_IMAGES

# Foreground service
services = Detection:service.py:foreground

p4a.branch = master
log_level = 2

[buildozer]
warn_on_root = 0
