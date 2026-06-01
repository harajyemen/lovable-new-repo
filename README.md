# Visual Assist

أداة مساعدة بصرية حية تعمل بالذكاء الاصطناعي المحلي على أجهزة Android. تلتقط
الشاشة لحظياً، تكتشف الأجسام السريعة/البعيدة في الألعاب، وترسم مربعات
فوسفورية عالية التباين لمساعدة المستخدمين على التتبّع البصري.

## المكوّنات
- `main.py` — واجهة Kivy + تدفّق الصلاحيات الحتمي.
- `offline_engine.py` — كشف + تتبّع KCF + Kalman للتنبؤ بالمسار.
- `overlay.py` — طبقة عرض شفافة فوق التطبيقات.
- `service.py` — Foreground Service مع إشعار دائم.
- `buildozer.spec` — إعدادات بناء APK (arm64-v8a، API 33).
- `.github/workflows/android_build.yml` — بناء تلقائي على GitHub Actions.

## النموذج
ضع ملفات الكشف داخل `assets/model/`:
- `yolov4-tiny.cfg`
- `yolov4-tiny.weights`
- `coco.names`

## البناء محلياً
```bash
pip install buildozer cython
buildozer -v android debug
```

## CI
يتم بناء APK تلقائياً على كل push للفرع `main` وإتاحته كـ artifact.
