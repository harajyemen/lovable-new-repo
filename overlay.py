# -*- coding: utf-8 -*-
"""
Visual Assist - Floating Neon Overlay (System Alert Window)
يرسم صناديق نيون متوهجة + ID + class + conf + FPS.
"""
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Rectangle, Ellipse
from kivy.core.text import Label as CoreLabel
from kivy.clock import Clock

NEON_PALETTE = [
    (0.10, 1.00, 0.55),  # green
    (0.20, 0.85, 1.00),  # cyan
    (1.00, 0.30, 0.60),  # magenta
    (1.00, 0.80, 0.10),  # amber
    (0.65, 0.40, 1.00),  # violet
]

class Overlay(Widget):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.detections = []
        self.fps = 0.0
        Clock.schedule_interval(self._redraw, 1/60.0)

    def push(self, detections, fps):
        self.detections = detections
        self.fps = fps

    def _color_for(self, tid):
        return NEON_PALETTE[tid % len(NEON_PALETTE)]

    def _redraw(self, *_):
        self.canvas.clear()
        with self.canvas:
            # HUD: FPS
            lbl = CoreLabel(text=f"FPS {self.fps:0.1f}", font_size=22, color=(0.2,1,0.6,1))
            lbl.refresh()
            tex = lbl.texture
            Color(0, 0, 0, 0.45)
            Rectangle(pos=(10, self.height-40), size=(tex.size[0]+12, tex.size[1]+8))
            Color(0.2,1,0.6,1)
            Rectangle(texture=tex, pos=(16, self.height-36), size=tex.size)

            for d in self.detections:
                x1,y1,x2,y2 = d["bbox"]
                # Kivy y is bottom-up
                yy1 = self.height - y2
                yy2 = self.height - y1
                w = x2 - x1; h = yy2 - yy1
                r,g,b = self._color_for(d["id"])
                # glow
                Color(r,g,b,0.18)
                Line(rectangle=(x1-3, yy1-3, w+6, h+6), width=4)
                Color(r,g,b,0.35)
                Line(rectangle=(x1-1, yy1-1, w+2, h+2), width=2.5)
                Color(r,g,b,1.0)
                Line(rectangle=(x1, yy1, w, h), width=1.6)
                # corner ticks
                tick = max(8, min(20, int(min(w,h)*0.12)))
                Line(points=[x1, yy1, x1+tick, yy1, x1, yy1, x1, yy1+tick], width=2)
                Line(points=[x2, yy1, x2-tick, yy1, x2, yy1, x2, yy1+tick], width=2)
                Line(points=[x1, yy2, x1+tick, yy2, x1, yy2, x1, yy2-tick], width=2)
                Line(points=[x2, yy2, x2-tick, yy2, x2, yy2, x2, yy2-tick], width=2)
                # tag
                tag = f"#{d['id']} {d['cls']} {d['conf']*100:0.0f}%"
                cl = CoreLabel(text=tag, font_size=16, color=(1,1,1,1))
                cl.refresh(); t = cl.texture
                Color(0,0,0,0.55)
                Rectangle(pos=(x1, yy2+4), size=(t.size[0]+10, t.size[1]+6))
                Color(r,g,b,1)
                Rectangle(texture=t, pos=(x1+5, yy2+7), size=t.size)
