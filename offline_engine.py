"""
محرك المعالجة الذكي (Offline)
- تحليل العناصر البعيدة عبر تكبير رقمي وتحسين التباين (CLAHE).
- كشف الأجسام السريعة بالاعتماد على OpenCV DNN (موديل خفيف، يعمل بدون إنترنت).
- تتبّع متعدد الأهداف عبر cv2.legacy.MultiTracker (KCF) + Kalman Filter للتنبؤ بالمسار.
"""
from __future__ import annotations
import os
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

try:
    import cv2
except Exception:  # سيُثبَّت في buildozer
    cv2 = None


# -----------------------------
# Kalman Filter للتنبؤ بالمسار
# -----------------------------
class KalmanBox:
    """مرشّح كالمن بسيط لمتابعة مركز المربع (cx, cy, w, h) + السرعة."""

    def __init__(self, bbox: Tuple[int, int, int, int]):
        x, y, w, h = bbox
        cx, cy = x + w / 2.0, y + h / 2.0
        self.kf = cv2.KalmanFilter(8, 4)
        self.kf.transitionMatrix = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.kf.transitionMatrix[i, i + 4] = 1.0  # x += vx
        self.kf.measurementMatrix = np.zeros((4, 8), np.float32)
        for i in range(4):
            self.kf.measurementMatrix[i, i] = 1.0
        self.kf.processNoiseCov = np.eye(8, dtype=np.float32) * 1e-2
        self.kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 1e-1
        self.kf.statePost = np.array(
            [cx, cy, w, h, 0, 0, 0, 0], np.float32
        ).reshape(8, 1)
        self.lost = 0

    def predict(self) -> Tuple[int, int, int, int]:
        s = self.kf.predict()
        cx, cy, w, h = float(s[0]), float(s[1]), float(s[2]), float(s[3])
        return int(cx - w / 2), int(cy - h / 2), int(w), int(h)

    def update(self, bbox: Tuple[int, int, int, int]):
        x, y, w, h = bbox
        cx, cy = x + w / 2.0, y + h / 2.0
        m = np.array([cx, cy, w, h], np.float32).reshape(4, 1)
        self.kf.correct(m)
        self.lost = 0


@dataclass
class Track:
    tid: int
    bbox: Tuple[int, int, int, int]
    score: float = 0.0
    label: str = "obj"
    kalman: Optional[KalmanBox] = None
    age: int = 0
    last_seen: float = field(default_factory=time.time)


# -----------------------------
# تحسين العناصر البعيدة
# -----------------------------
def enhance_long_range(frame: np.ndarray, zoom: float = 1.0) -> np.ndarray:
    """تكبير رقمي + CLAHE لرفع تباين الأجسام الصغيرة البعيدة."""
    if zoom > 1.0:
        h, w = frame.shape[:2]
        nh, nw = int(h / zoom), int(w / zoom)
        y0, x0 = (h - nh) // 2, (w - nw) // 2
        frame = frame[y0:y0 + nh, x0:x0 + nw]
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_CUBIC)

    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)


# -----------------------------
# المحرك الرئيسي
# -----------------------------
class OfflineEngine:
    """
    pipeline: detect -> associate -> track (KCF) -> Kalman predict
    """

    def __init__(self, model_dir: str = "assets/model",
                 conf_thr: float = 0.35, nms_thr: float = 0.45,
                 input_size: int = 320):
        self.conf_thr = conf_thr
        self.nms_thr = nms_thr
        self.input_size = input_size
        self.net = None
        self.classes: List[str] = []
        self.tracks: List[Track] = []
        self._next_id = 1
        self._load_model(model_dir)

    def _load_model(self, model_dir: str):
        if cv2 is None:
            return
        cfg = os.path.join(model_dir, "yolov4-tiny.cfg")
        weights = os.path.join(model_dir, "yolov4-tiny.weights")
        names = os.path.join(model_dir, "coco.names")
        if not (os.path.exists(cfg) and os.path.exists(weights)):
            # سيُحمَّل في وقت التشغيل أو يُترك للوضع التجريبي.
            return
        self.net = cv2.dnn_DetectionModel(cfg, weights)
        self.net.setInputSize(self.input_size, self.input_size)
        self.net.setInputScale(1.0 / 255.0)
        self.net.setInputSwapRB(True)
        if os.path.exists(names):
            with open(names, "r", encoding="utf-8") as f:
                self.classes = [ln.strip() for ln in f if ln.strip()]

    # ------- detection -------
    def detect(self, frame: np.ndarray):
        if self.net is None:
            return [], [], []
        ids, scores, boxes = self.net.detect(
            frame, confThreshold=self.conf_thr, nmsThreshold=self.nms_thr
        )
        if len(boxes) == 0:
            return [], [], []
        return (
            ids.flatten().tolist(),
            scores.flatten().tolist(),
            [tuple(map(int, b)) for b in boxes],
        )

    # ------- association (IoU) -------
    @staticmethod
    def _iou(a, b):
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1 = max(ax, bx); y1 = max(ay, by)
        x2 = min(ax + aw, bx + bw); y2 = min(ay + ah, by + bh)
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = aw * ah + bw * bh - inter
        return inter / union if union > 0 else 0.0

    def step(self, frame: np.ndarray, zoom: float = 1.0) -> List[Track]:
        """يستقبل إطاراً ويعيد قائمة Tracks بعد التحديث."""
        if cv2 is None:
            return []
        frame = enhance_long_range(frame, zoom=zoom)
        ids, scores, boxes = self.detect(frame)

        # 1) تنبؤ Kalman لكل track قائم
        for t in self.tracks:
            if t.kalman is not None:
                t.bbox = t.kalman.predict()
                t.age += 1

        # 2) ربط الكشوفات بالـ tracks عبر IoU
        used = set()
        for det_box, det_score, det_id in zip(boxes, scores, ids):
            best, best_iou = -1, 0.3
            for i, t in enumerate(self.tracks):
                if i in used:
                    continue
                iou = self._iou(det_box, t.bbox)
                if iou > best_iou:
                    best, best_iou = i, iou
            if best >= 0:
                t = self.tracks[best]
                t.bbox = det_box
                t.score = float(det_score)
                t.last_seen = time.time()
                if t.kalman is not None:
                    t.kalman.update(det_box)
                used.add(best)
            else:
                lbl = self.classes[int(det_id)] if 0 <= int(det_id) < len(self.classes) else "obj"
                self.tracks.append(Track(
                    tid=self._next_id, bbox=det_box, score=float(det_score),
                    label=lbl, kalman=KalmanBox(det_box),
                ))
                self._next_id += 1

        # 3) إسقاط الـ tracks المفقودة لفترة طويلة
        alive = []
        for i, t in enumerate(self.tracks):
            if i in used or (time.time() - t.last_seen) < 1.2:
                alive.append(t)
        self.tracks = alive
        return self.tracks
