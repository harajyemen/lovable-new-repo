"""
Visual Assist - نقطة الإقلاع الآمن
واجهة Kivy بسيطة + طلب الصلاحيات الحتمية (Media Projection, Overlay, Storage, Foreground Service).
لا ينهار التطبيق إذا رفض المستخدم — يبقى في حالة انتظار مع رسالة توجيهية.
"""
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.utils import platform

REQUIRED_PERMS = []
if platform == "android":
    from android.permissions import (
        request_permissions, check_permission, Permission
    )
    REQUIRED_PERMS = [
        Permission.FOREGROUND_SERVICE,
        Permission.SYSTEM_ALERT_WINDOW,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.POST_NOTIFICATIONS,
    ]


class RootUI(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", padding=24, spacing=16, **kw)
        self.status = Label(
            text="مرحباً بك\nاضغط بدء لمنح الصلاحيات وتشغيل المساعد البصري",
            halign="center", valign="middle", font_size=18,
        )
        self.status.bind(size=lambda *_: setattr(
            self.status, "text_size", self.status.size))
        self.btn_start = Button(text="بدء المساعد البصري", size_hint_y=None, height=64)
        self.btn_start.bind(on_release=self.on_start)
        self.btn_overlay = Button(text="منح صلاحية العرض فوق التطبيقات",
                                  size_hint_y=None, height=56)
        self.btn_overlay.bind(on_release=self.request_overlay)
        self.btn_projection = Button(text="منح صلاحية التقاط الشاشة",
                                     size_hint_y=None, height=56)
        self.btn_projection.bind(on_release=self.request_projection)

        self.add_widget(self.status)
        self.add_widget(self.btn_overlay)
        self.add_widget(self.btn_projection)
        self.add_widget(self.btn_start)

    # --- Permissions flow ---
    def request_runtime_perms(self, cb):
        if platform != "android":
            cb(True); return
        missing = [p for p in REQUIRED_PERMS if not check_permission(p)]
        if not missing:
            cb(True); return

        def _result(perms, grants):
            cb(all(grants))
        request_permissions(missing, _result)

    def request_overlay(self, *_):
        if platform != "android":
            self.set_status("Overlay (محاكاة سطح المكتب) ✔"); return
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            Settings = autoclass("android.provider.Settings")
            Uri = autoclass("android.net.Uri")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            act = PythonActivity.mActivity
            intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                            Uri.parse("package:" + act.getPackageName()))
            act.startActivity(intent)
            self.set_status("افتح الإعدادات وفعّل العرض فوق التطبيقات، ثم عد للتطبيق.")
        except Exception as e:
            self.set_status(f"تعذّر فتح إعدادات الـ Overlay:\n{e}")

    def request_projection(self, *_):
        """يفتح حوار MediaProjection الرسمي عبر الخدمة."""
        if platform != "android":
            self.set_status("MediaProjection (محاكاة) ✔"); return
        try:
            from jnius import autoclass
            Intent = autoclass("android.content.Intent")
            PythonActivity = autoclass("org.kivy.android.PythonActivity")
            act = PythonActivity.mActivity
            # سيتم التقاط الحوار من جانب Java/Service لاحقاً.
            # هنا نطلب من المستخدم تأكيد الصلاحية ثم نشغّل الخدمة.
            self.set_status("سيتم طلب إذن التقاط الشاشة عند بدء التشغيل.")
        except Exception as e:
            self.set_status(f"خطأ: {e}")

    def on_start(self, *_):
        self.set_status("جاري طلب الصلاحيات...")

        def after(ok):
            if not ok:
                self.set_status(
                    "لم تُمنح كل الصلاحيات.\nسأنتظر — افتح الإعدادات وامنحها ثم اضغط بدء مجدداً."
                )
                return
            self.start_service()
        self.request_runtime_perms(after)

    def start_service(self):
        self.set_status("تم منح الصلاحيات. تشغيل الخدمة الخلفية...")
        if platform != "android":
            return
        try:
            from jnius import autoclass
            service = autoclass(
                "org.visualassist.app.ServiceVisualassist"
            )
            mActivity = autoclass("org.kivy.android.PythonActivity").mActivity
            argument = ""
            service.start(mActivity, argument)
            self.set_status("الخدمة تعمل في الخلفية ✔\nابدأ اللعبة الآن.")
        except Exception as e:
            self.set_status(f"تعذّر تشغيل الخدمة:\n{e}")

    def set_status(self, msg):
        Clock.schedule_once(lambda *_: setattr(self.status, "text", msg), 0)


class VisualAssistApp(App):
    title = "Visual Assist"

    def build(self):
        return RootUI()


if __name__ == "__main__":
    VisualAssistApp().run()
