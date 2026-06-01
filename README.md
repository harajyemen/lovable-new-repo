# Visual Assist — أقوى نظام كشف بصري محلي (Offline)

تطبيق أندرويد مفتوح المصدر يساعد ضعاف البصر عبر طبقة عرض شفافة فوق الشاشة تُحدّد الأهداف
وتتعقّبها في الوقت الفعلي — بدون إنترنت.

## المحرك (الأقوى)
- **كاشف:** YOLOv8n ONNX عبر OpenCV DNN
- **استدلال مقسّم (SAHI-like):** بلاطات 640×640 بتداخل 25% لاكتشاف الأهداف الصغيرة جداً
- **تحسين الصورة:** CLAHE + Unsharp Mask + ESPCN ×2 Super-Resolution للمدى البعيد
- **تتبّع متعدد الأهداف:** ByteTrack-like + Kalman Filter (constant velocity)
- **TTA اختياري:** flip augmentation لرفع الاسترجاع
- **NMS هجين:** per-class + class-agnostic

## ملفات النماذج المطلوبة (ضعها في جذر المشروع قبل البناء)
- `yolov8n.onnx` — صدّره من Ultralytics:
  ```bash
  pip install ultralytics
  yolo export model=yolov8n.pt format=onnx imgsz=640 opset=12
  ```
- `espcn_x2.pb` (اختياري للمدى البعيد) — من OpenCV Zoo.

## البناء التلقائي
ادفع إلى `main` وسيُنتج GitHub Actions حزمة APK في `bin/*.apk` (Artifact).

## الترخيص
MIT.
