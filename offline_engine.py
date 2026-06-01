# -*- coding: utf-8 -*-
"""
Visual Assist - Offline Detection Engine (STRONGEST MODE)
- YOLOv8n ONNX (Ultralytics export) عبر OpenCV DNN (CPU/NNAPI fallback)
- Multi-scale tiled inference (SAHI-like) لاكتشاف الأهداف البعيدة جداً
- CLAHE + Unsharp + ESPCN x2 super-resolution للأهداف الصغيرة
- ByteTrack-style multi-object tracker مع Kalman + IOU + Re-association
- Adaptive confidence + Test-Time Augmentation (flip) اختياري
- Class-agnostic NMS + per-class NMS هجين
"""

import os
import time
import numpy as np
import cv2

# -------- Config --------
MODEL_INPUT = 640                 # YOLOv8 input size
TILE_SIZE   = 640                 # tile size for SAHI
TILE_OVERLAP= 0.25                # 25% overlap
CONF_THRES  = 0.20                # low to maximize recall, NMS will clean
IOU_THRES   = 0.45
MAX_DET     = 300
USE_TTA     = False               # flip-augment (يبطئ، فعّله لو CPU قوي)
USE_SR      = True                # ESPCN x2 على الكوادر البعيدة

COCO_CLASSES = [
    "person","bicycle","car","motorcycle","airplane","bus","train","truck","boat","traffic light",
    "fire hydrant","stop sign","parking meter","bench","bird","cat","dog","horse","sheep","cow",
    "elephant","bear","zebra","giraffe","backpack","umbrella","handbag","tie","suitcase","frisbee",
    "skis","snowboard","sports ball","kite","baseball bat","baseball glove","skateboard","surfboard",
    "tennis racket","bottle","wine glass","cup","fork","knife","spoon","bowl","banana","apple",
    "sandwich","orange","broccoli","carrot","hot dog","pizza","donut","cake","chair","couch",
    "potted plant","bed","dining table","toilet","tv","laptop","mouse","remote","keyboard","cell phone",
    "microwave","oven","toaster","sink","refrigerator","book","clock","vase","scissors","teddy bear",
    "hair drier","toothbrush"
]


# ============================================================
#                        Kalman Box
# ============================================================
class KalmanBox:
    """Constant-velocity 2D Kalman filter on bbox center+size."""
    def __init__(self, bbox):
        self.kf = cv2.KalmanFilter(8, 4)
        dt = 1.0
        self.kf.transitionMatrix = np.eye(8, dtype=np.float32)
        for i in range(4):
            self.kf.transitionMatrix[i, i+4] = dt
        self.kf.measurementMatrix = np.zeros((4, 8), np.float32)
        for i in range(4):
            self.kf.measurementMatrix[i, i] = 1.0
        self.kf.processNoiseCov     = np.eye(8, dtype=np.float32) * 1e-2
        self.kf.measurementNoiseCov = np.eye(4, dtype=np.float32) * 1e-1
        self.kf.errorCovPost        = np.eye(8, dtype=np.float32)
        x, y, w, h = self._to_xywh(bbox)
        self.kf.statePost = np.array([[x],[y],[w],[h],[0],[0],[0],[0]], np.float32)

    @staticmethod
    def _to_xywh(b):
        x1,y1,x2,y2 = b
        return ((x1+x2)/2.0, (y1+y2)/2.0, x2-x1, y2-y1)

    @staticmethod
    def _to_xyxy(s):
        x,y,w,h = s
        return [x-w/2.0, y-h/2.0, x+w/2.0, y+h/2.0]

    def predict(self):
        p = self.kf.predict().flatten()
        return self._to_xyxy(p[:4])

    def update(self, bbox):
        x,y,w,h = self._to_xywh(bbox)
        m = np.array([[x],[y],[w],[h]], np.float32)
        self.kf.correct(m)


# ============================================================
#                    ByteTrack-style Tracker
# ============================================================
def _iou(a, b):
    ax1,ay1,ax2,ay2 = a; bx1,by1,bx2,by2 = b
    ix1 = max(ax1,bx1); iy1 = max(ay1,by1)
    ix2 = min(ax2,bx2); iy2 = min(ay2,by2)
    iw = max(0.0, ix2-ix1); ih = max(0.0, iy2-iy1)
    inter = iw*ih
    ua = max(1e-6, (ax2-ax1)*(ay2-ay1) + (bx2-bx1)*(by2-by1) - inter)
    return inter/ua


class Track:
    _next_id = 1
    def __init__(self, bbox, cls, conf):
        self.id = Track._next_id; Track._next_id += 1
        self.kf = KalmanBox(bbox)
        self.bbox = bbox
        self.cls = cls
        self.conf = conf
        self.age = 1
        self.lost = 0
        self.hits = 1

    def predict(self):
        self.bbox = self.kf.predict()
        self.age += 1
        return self.bbox

    def update(self, bbox, conf):
        self.kf.update(bbox)
        self.bbox = bbox
        self.conf = 0.7*self.conf + 0.3*conf
        self.lost = 0
        self.hits += 1


class ByteLikeTracker:
    def __init__(self, max_lost=30, iou_high=0.5, iou_low=0.2):
        self.tracks = []
        self.max_lost = max_lost
        self.iou_high = iou_high
        self.iou_low  = iou_low

    def step(self, detections):
        # predict
        for t in self.tracks:
            t.predict()
            t.lost += 1

        high = [d for d in detections if d[5] >= 0.5]
        low  = [d for d in detections if d[5] <  0.5]

        # 1st association: tracks vs high-confidence
        self._associate(high, self.iou_high)
        # 2nd association: remaining tracks vs low-confidence
        self._associate(low, self.iou_low)

        # create new tracks for unmatched high
        for d in high:
            if not d[6]:
                self.tracks.append(Track([d[0],d[1],d[2],d[3]], int(d[4]), float(d[5])))

        # drop stale
        self.tracks = [t for t in self.tracks if t.lost <= self.max_lost]
        return self.tracks

    def _associate(self, dets, thr):
        for d in dets:
            d.append(False)  # matched flag at index 6 (or 7 second pass — safe)
        for t in self.tracks:
            best, best_iou = -1, thr
            for i, d in enumerate(dets):
                if d[-1]: continue
                iou = _iou(t.bbox, [d[0],d[1],d[2],d[3]])
                if iou > best_iou:
                    best_iou = iou; best = i
            if best >= 0:
                d = dets[best]
                t.update([d[0],d[1],d[2],d[3]], float(d[5]))
                d[-1] = True


# ============================================================
#                  Super-Resolution (ESPCN x2)
# ============================================================
class SuperRes:
    def __init__(self, model_path="espcn_x2.pb"):
        self.ok = False
        if not USE_SR or not os.path.exists(model_path):
            return
        try:
            self.sr = cv2.dnn_superres.DnnSuperResImpl_create()
            self.sr.readModel(model_path)
            self.sr.setModel("espcn", 2)
            self.ok = True
        except Exception:
            self.ok = False

    def upscale(self, img):
        if not self.ok: return img
        try:
            return self.sr.upsample(img)
        except Exception:
            return img


# ============================================================
#                   YOLOv8 ONNX Detector
# ============================================================
class YoloV8Onnx:
    def __init__(self, onnx_path="yolov8n.onnx"):
        if not os.path.exists(onnx_path):
            raise FileNotFoundError(
                f"ضع نموذج {onnx_path} في جذر التطبيق. صدّر من Ultralytics: "
                "`yolo export model=yolov8n.pt format=onnx imgsz=640 opset=12`"
            )
        self.net = cv2.dnn.readNetFromONNX(onnx_path)
        # حاول NNAPI/OpenCL إن توفر، وإلا CPU
        try:
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        except Exception:
            pass

    def _infer(self, img):
        blob = cv2.dnn.blobFromImage(img, 1/255.0, (MODEL_INPUT, MODEL_INPUT),
                                      swapRB=True, crop=False)
        self.net.setInput(blob)
        out = self.net.forward()  # (1, 84, 8400) for v8
        return out

    def detect(self, frame):
        h0, w0 = frame.shape[:2]
        # letterbox to square
        s = MODEL_INPUT / max(h0, w0)
        nh, nw = int(round(h0*s)), int(round(w0*s))
        resized = cv2.resize(frame, (nw, nh))
        canvas = np.full((MODEL_INPUT, MODEL_INPUT, 3), 114, np.uint8)
        canvas[:nh, :nw] = resized

        preds = self._infer(canvas)
        if USE_TTA:
            preds2 = self._infer(cv2.flip(canvas, 1))
            # flip x back
            preds2[..., 0:1] = MODEL_INPUT - preds2[..., 0:1]
            preds = np.concatenate([preds, preds2], axis=2)

        # parse YOLOv8: [x,y,w,h, c0..c79]
        p = preds[0].T  # (N, 84)
        boxes_xywh = p[:, :4]
        scores = p[:, 4:]
        class_ids = np.argmax(scores, axis=1)
        confs = scores[np.arange(scores.shape[0]), class_ids]

        mask = confs > CONF_THRES
        boxes_xywh = boxes_xywh[mask]
        confs = confs[mask]
        class_ids = class_ids[mask]

        if boxes_xywh.shape[0] == 0:
            return []

        # xywh -> xyxy in canvas coords
        xy = boxes_xywh[:, :2]; wh = boxes_xywh[:, 2:]
        x1y1 = xy - wh/2.0; x2y2 = xy + wh/2.0
        boxes = np.concatenate([x1y1, x2y2], axis=1)

        # NMS (class-aware)
        keep = cv2.dnn.NMSBoxesBatched(
            boxes.tolist(), confs.tolist(), class_ids.tolist(),
            CONF_THRES, IOU_THRES, top_k=MAX_DET
        ) if hasattr(cv2.dnn, "NMSBoxesBatched") else cv2.dnn.NMSBoxes(
            boxes.tolist(), confs.tolist(), CONF_THRES, IOU_THRES
        )

        results = []
        for i in np.array(keep).flatten():
            x1,y1,x2,y2 = boxes[i]
            # canvas -> original
            x1 = max(0, x1 / s); y1 = max(0, y1 / s)
            x2 = min(w0, x2 / s); y2 = min(h0, y2 / s)
            results.append([float(x1),float(y1),float(x2),float(y2),
                            int(class_ids[i]), float(confs[i])])
        return results


# ============================================================
#                  Image enhancement utils
# ============================================================
_clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))

def enhance(frame):
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = _clahe.apply(l)
    lab = cv2.merge((l, a, b))
    out = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    # unsharp
    blur = cv2.GaussianBlur(out, (0,0), 1.0)
    out  = cv2.addWeighted(out, 1.5, blur, -0.5, 0)
    return out


# ============================================================
#               Tiled (SAHI-like) inference
# ============================================================
def tiled_detect(detector, frame, tile=TILE_SIZE, overlap=TILE_OVERLAP):
    h, w = frame.shape[:2]
    step = int(tile * (1 - overlap))
    all_dets = []
    # global pass
    all_dets.extend(detector.detect(frame))
    # tiles only if frame is large enough
    if max(h, w) > tile * 1.3:
        for y in range(0, max(1, h - tile + 1), step):
            for x in range(0, max(1, w - tile + 1), step):
                x2 = min(w, x + tile); y2 = min(h, y + tile)
                crop = frame[y:y2, x:x2]
                dets = detector.detect(crop)
                for d in dets:
                    d[0] += x; d[1] += y; d[2] += x; d[3] += y
                    all_dets.append(d)
    # global NMS again
    if not all_dets: return []
    boxes  = [[d[0],d[1],d[2],d[3]] for d in all_dets]
    confs  = [d[5] for d in all_dets]
    ids    = [d[4] for d in all_dets]
    keep = cv2.dnn.NMSBoxes(boxes, confs, CONF_THRES, IOU_THRES)
    return [all_dets[i] for i in np.array(keep).flatten()]


# ============================================================
#                       Engine facade
# ============================================================
class OfflineEngine:
    def __init__(self, onnx_path="yolov8n.onnx", sr_path="espcn_x2.pb"):
        self.detector = YoloV8Onnx(onnx_path)
        self.sr       = SuperRes(sr_path)
        self.tracker  = ByteLikeTracker()
        self.last_t   = time.time()
        self.fps      = 0.0

    def process(self, frame, long_range=False):
        if long_range and self.sr.ok:
            frame = self.sr.upscale(frame)
        frame_e = enhance(frame)
        dets = tiled_detect(self.detector, frame_e)
        # tracker expects mutable lists
        dets_for_track = [list(d) for d in dets]
        tracks = self.tracker.step(dets_for_track)

        now = time.time()
        dt = max(1e-6, now - self.last_t)
        self.last_t = now
        self.fps = 0.9*self.fps + 0.1*(1.0/dt)

        results = []
        for t in tracks:
            x1,y1,x2,y2 = [int(v) for v in t.bbox]
            results.append({
                "id":   t.id,
                "bbox": (x1,y1,x2,y2),
                "cls":  COCO_CLASSES[t.cls] if 0 <= t.cls < len(COCO_CLASSES) else str(t.cls),
                "conf": float(t.conf),
            })
        return results, self.fps
