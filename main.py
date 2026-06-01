# -*- coding: utf-8 -*-
"""
Visual Assist - Main UI (Kivy)
- يطلب صلاحيات Android (SYSTEM_ALERT_WINDOW, FOREGROUND_SERVICE, MediaProjection)
- لا ينهار في حالة الرفض، يعرض رسالة واضحة.
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.floatlayout import FloatLayout
from kivy.clock import Clock

from overlay import Overlay
from service import DetectionService

import numpy as np

IS_ANDROID = False
try:
    from android.permissions import request_permissions, Permission  # type: ignore
    from jnius import autoclass  # type: ignore
    IS_ANDROID = True
except Exception:
    pass


def dummy_frame():
    # placeholder بإطار اختباري للديسكتوب
    img = (np.random.rand(480, 640, 3) * 255).astype(np.uint8)
    return img


class Root(FloatLayout):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.overlay = Overlay(size_hint=(1, 1))
        self.add_widget(self.overlay)

        bar = BoxLayout(orientation="horizontal", size_hint=(1, None), height=72,
                        pos_hint={"x": 0, "y": 0}, padding=8, spacing=8)
        self.status = Label(text="Visual Assist — جاهز", color=(0.9,1,0.95,1))
        self.btn_toggle = Button(text="ابدأ", on_release=self.toggle)
        self.btn_lr     = Button(text="مدى بعيد: OFF", on_release=self.toggle_lr)
        bar.add_widget(self.status); bar.add_widget(self.btn_lr); bar.add_widget(self.btn_toggle)
        self.add_widget(bar)

        self.service = DetectionService(frame_source=dummy_frame, overlay=self.overlay)
        Clock.schedule_once(self._request_perms, 0.5)

    def _request_perms(self, *_):
        if not IS_ANDROID:
            self.status.text = "وضع المعاينة (ديسكتوب)"
            return
        try:
            request_permissions([
                Permission.FOREGROUND_SERVICE,
                Permission.POST_NOTIFICATIONS,
                Permission.READ_MEDIA_IMAGES,
                Permission.RECORD_AUDIO,
            ], self._after_perms)
        except Exception as e:
            self.status.text = f"تعذر طلب الصلاحيات: {e}"

    def _after_perms(self, perms, grants):
        ok = all(grants) if grants else False
        self.status.text = "تم منح الصلاحيات" if ok else "بعض الصلاحيات مرفوضة — يعمل بقيود"

    def toggle(self, *_):
        if self.service.running:
            self.service.stop()
            self.btn_toggle.text = "ابدأ"
            self.status.text = "متوقف"
        else:
            self.service.start()
            self.btn_toggle.text = "إيقاف"
            self.status.text = "يعمل — كشف مباشر"

    def toggle_lr(self, *_):
        on = self.service.toggle_long_range()
        self.btn_lr.text = f"مدى بعيد: {'ON' if on else 'OFF'}"


class VisualAssistApp(App):
    def build(self):
        self.title = "Visual Assist"
        return Root()


if __name__ == "__main__":
    VisualAssistApp().run()
