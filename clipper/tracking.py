"""Seguimiento facial con OpenCV para recortar el clip siguiendo a la persona.

Usa el detector YuNet de OpenCV (preciso, corre en CPU). Si no puede descargar el
modelo, usa el clasificador Haar que viene incluido en OpenCV.
"""
import os
import urllib.request
from pathlib import Path

import cv2
import numpy as np

YUNET_URL = ("https://github.com/opencv/opencv_zoo/raw/main/models/"
             "face_detection_yunet/face_detection_yunet_2023mar.onnx")
CACHE = Path(os.environ.get("CLIPPER_CACHE", Path.home() / ".cache" / "clipper"))


class FaceDetector:
    def __init__(self):
        self.yunet = None
        model = CACHE / "yunet.onnx"
        try:
            if not model.exists():
                CACHE.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(YUNET_URL, model)
            self.yunet = cv2.FaceDetectorYN.create(str(model), "", (320, 320), 0.7)
        except Exception as e:
            print(f"    (YuNet no disponible: {e}; uso Haar)")
            model.unlink(missing_ok=True)
            self.haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

    def largest(self, frame) -> tuple[float, float, float, float] | None:
        """Devuelve (cx, cy, w, h) de la cara más grande, o None."""
        h, w = frame.shape[:2]
        scale = 640 / max(w, h)
        small = cv2.resize(frame, (int(w * scale), int(h * scale)))
        if self.yunet is not None:
            self.yunet.setInputSize((small.shape[1], small.shape[0]))
            _, faces = self.yunet.detect(small)
            boxes = [] if faces is None else [f[:4] for f in faces]
        else:
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            boxes = self.haar.detectMultiScale(gray, 1.1, 6, minSize=(24, 24))
        if len(boxes) == 0:
            return None
        x, y, bw, bh = max(boxes, key=lambda b: b[2] * b[3])
        return ((x + bw / 2) / scale, (y + bh / 2) / scale, bw / scale, bh / scale)


def track(video_path: Path, samples_per_second: float = 5) -> tuple[list, float, int]:
    """Detecta la cara principal a lo largo del video.

    Devuelve (detecciones por frame — None donde no se muestreó o no hubo cara, fps, n_frames).
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, round(fps / samples_per_second))
    det = FaceDetector()
    out, i = [], 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        out.append(det.largest(frame) if i % step == 0 else None)
        i += 1
    cap.release()
    return out, fps, i


def smooth_path(dets: list, n_frames: int, src_w: int, deadzone: float = 0.06, ease: float = 0.08):
    """Convierte detecciones sueltas en un movimiento de cámara suave (sin temblores).

    Devuelve un array con el centro X de la cara para cada frame, o None si no hubo caras.
    """
    idx = [i for i, d in enumerate(dets) if d is not None]
    if len(idx) < 3:
        return None
    target = np.interp(np.arange(n_frames), idx, [dets[i][0] for i in idx])
    cam = np.empty(n_frames)
    cam[0] = target[0]
    for f in range(1, n_frames):
        diff = target[f] - cam[f - 1]
        # zona muerta: solo mueve la cámara si la cara se aleja lo suficiente del centro
        cam[f] = cam[f - 1] + (diff * ease if abs(diff) > deadzone * src_w else diff * ease * 0.1)
    return cam


def facecam_box(dets: list) -> tuple[float, float, float] | None:
    """Posición estable de la facecam (mediana): (cx, cy, alto_cara)."""
    found = [d for d in dets if d is not None]
    if len(found) < 3:
        return None
    a = np.median(np.array(found), axis=0)
    return float(a[0]), float(a[1]), float(a[3])
