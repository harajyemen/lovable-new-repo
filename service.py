# -*- coding: utf-8 -*-
"""
Visual Assist - Foreground Service @ up to 60 FPS
يلتقط الإطار عبر MediaProjection -> OfflineEngine -> Overlay
"""
import time, threading, traceback
from offline_engine import OfflineEngine

TARGET_FPS = 60
FRAME_DT   = 1.0 / TARGET_FPS

class DetectionService:
    def __init__(self, frame_source, overlay):
        self.frame_source = frame_source     # callable -> BGR np.ndarray | None
        self.overlay      = overlay
        self.engine       = OfflineEngine()
        self.running      = False
        self.long_range   = False
        self._t           = None

    def start(self):
        if self.running: return
        self.running = True
        self._t = threading.Thread(target=self._loop, daemon=True)
        self._t.start()

    def stop(self):
        self.running = False

    def toggle_long_range(self):
        self.long_range = not self.long_range
        return self.long_range

    def _loop(self):
        while self.running:
            t0 = time.time()
            try:
                frame = self.frame_source()
                if frame is not None:
                    dets, fps = self.engine.process(frame, long_range=self.long_range)
                    if self.overlay is not None:
                        self.overlay.push(dets, fps)
            except Exception:
                traceback.print_exc()
            dt = time.time() - t0
            if dt < FRAME_DT:
                time.sleep(FRAME_DT - dt)
