"""
الخدمة الأمامية (Foreground Service)
- تُشغَّل عبر pyjnius من main.py (ServiceVisualassist يتولّد تلقائياً بفضل
  services في buildozer.spec).
- تستقبل دفق MediaProjection، تمرّره إلى OfflineEngine، وتحدّث FloatingOverlay.
- تُظهر إشعاراً دائماً لمنع نظام الأندرويد من إغلاق العملية.
"""
from __future__ import annotations
import time
import traceback

import numpy as np

from offline_engine import OfflineEngine
from overlay import FloatingOverlay

TARGET_FPS = 60
FRAME_DT = 1.0 / TARGET_FPS


def show_persistent_notification():
    try:
        from jnius import autoclass
        PythonService = autoclass("org.kivy.android.PythonService")
        service = PythonService.mService
        NotificationBuilder = autoclass("android.app.Notification$Builder")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        NotificationManager = autoclass("android.app.NotificationManager")
        Context = autoclass("android.content.Context")
        String = autoclass("java.lang.String")

        channel_id = String("visualassist_channel")
        nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
        channel = NotificationChannel(
            channel_id, String("Visual Assist"),
            NotificationManager.IMPORTANCE_LOW,
        )
        nm.createNotificationChannel(channel)

        nb = NotificationBuilder(service, channel_id)
        nb.setContentTitle(String("Visual Assist يعمل"))
        nb.setContentText(String("تتبّع بصري لحظي للألعاب"))
        nb.setSmallIcon(service.getApplicationInfo().icon)
        nb.setOngoing(True)
        service.startForeground(0x4242, nb.build())
    except Exception:
        traceback.print_exc()


def capture_loop():
    """
    حلقة الالتقاط الرئيسية. في الإنتاج تُغذّى الإطارات من MediaProjection
    عبر VirtualDisplay + ImageReader (Java side). هنا نطبّق إطار اختبار أسود
    لضمان عمل الـ pipeline حتى لو لم يُمرَّر مصدر حقيقي.
    """
    engine = OfflineEngine(model_dir="assets/model")
    overlay = FloatingOverlay()

    last = time.time()
    while True:
        now = time.time()
        dt = now - last
        if dt < FRAME_DT:
            time.sleep(FRAME_DT - dt)
        last = time.time()

        try:
            frame = _grab_frame()  # يجب أن يعيد ndarray BGR
            if frame is None:
                continue
            tracks = engine.step(frame, zoom=1.2)
            boxes = [
                (t.bbox[0], t.bbox[1], t.bbox[2], t.bbox[3], t.label)
                for t in tracks
            ]
            overlay.update(boxes)
        except Exception:
            traceback.print_exc()
            time.sleep(0.05)


def _grab_frame():
    """واجهة استبدال: يجب أن تُربط بـ MediaProjection ImageReader.
    حالياً تعيد None حتى تُربط بإطارات حقيقية."""
    return None


if __name__ == "__main__":
    show_persistent_notification()
    capture_loop()
