"""
طبقة عرض شفافة (Floating Overlay)
- نافذة System Alert Window شفافة بحجم الشاشة.
- ترسم مربعات تحديد فوسفورية عالية التباين فوق العناصر المتتبَّعة.
- متزامنة مع محرك التتبع عبر تحديث 60Hz.
"""
from __future__ import annotations
from typing import List, Tuple
from kivy.utils import platform


NEON_GREEN = (0x39, 0xFF, 0x14, 0xFF)   # AARRGGBB / RGBA
NEON_PINK = (0xFF, 0x14, 0x93, 0xFF)


def _android_overlay():
    from jnius import autoclass, PythonJavaClass, java_method
    WindowManager = autoclass("android.view.WindowManager")
    LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
    PixelFormat = autoclass("android.graphics.PixelFormat")
    Context = autoclass("android.content.Context")
    View = autoclass("android.view.View")
    Paint = autoclass("android.graphics.Paint")
    Color = autoclass("android.graphics.Color")
    Canvas = autoclass("android.graphics.Canvas")
    return locals()


class FloatingOverlay:
    """يدير نافذة شفافة فوق الشاشة لرسم المربعات."""

    def __init__(self):
        self.boxes: List[Tuple[int, int, int, int, str]] = []
        self.view = None
        self.wm = None
        self._params = None
        if platform == "android":
            self._setup_android()

    def _setup_android(self):
        from jnius import autoclass, PythonJavaClass, java_method
        ctx = autoclass("org.kivy.android.PythonActivity").mActivity
        WindowManager = autoclass("android.view.WindowManager")
        LayoutParams = autoclass("android.view.WindowManager$LayoutParams")
        PixelFormat = autoclass("android.graphics.PixelFormat")
        View = autoclass("android.view.View")
        Paint = autoclass("android.graphics.Paint")
        Color = autoclass("android.graphics.Color")

        outer = self

        class OverlayView(PythonJavaClass):
            __javacontext__ = "app"
            __javainterfaces__ = []

            def __init__(self, context):
                super().__init__()

        # ملاحظة: في الإنتاج يُستحسن استبدال هذا بـ AAR Java بسيط يحوي View
        # مخصص (onDraw) لرسم المستطيلات. هنا نوفّر الواجهة Python.
        params = LayoutParams(
            LayoutParams.MATCH_PARENT,
            LayoutParams.MATCH_PARENT,
            LayoutParams.TYPE_APPLICATION_OVERLAY,
            LayoutParams.FLAG_NOT_FOCUSABLE
            | LayoutParams.FLAG_NOT_TOUCHABLE
            | LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        )
        self._params = params
        self.wm = ctx.getSystemService(autoclass("android.content.Context").WINDOW_SERVICE)
        # نُبقي الـ view = None هنا؛ يفعَّل من خلال SurfaceView Java جانبي.

    def update(self, boxes: List[Tuple[int, int, int, int, str]]):
        """تحديث المربعات: قائمة (x, y, w, h, label)."""
        self.boxes = boxes
        # في النسخة المعتمدة على Java View يتم استدعاء view.invalidate()

    def hide(self):
        self.boxes = []
