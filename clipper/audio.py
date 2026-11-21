"""Análisis de volumen: encuentra reacciones (gritos, risas, explosiones) en videos y streams."""
import subprocess

import numpy as np

RATE = 8000
STEP = 0.5  # segundos por ventana


class Loudness:
    """Curva de volumen del video completo (una medición cada 0,5 s). Rápido incluso en streams de horas."""

    def __init__(self, video_path):
        raw = subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(RATE),
             "-f", "s16le", "pipe:1"],
            check=True, capture_output=True,
        ).stdout
        pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        win = int(RATE * STEP)
        n = pcm.size // win
        self.duration = n * STEP
        if n == 0:
            self.db, self.base = np.zeros(0), 0.0
            return
        rms = np.sqrt(np.mean(pcm[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-6
        self.db = 20 * np.log10(rms)
        self.base = float(np.median(self.db))

    def annotate(self, segments: list[dict], threshold_db: float = 6.0) -> None:
        """Agrega `loud_db` a los segmentos cuyo pico supera el volumen típico."""
        n = len(self.db)
        for s in segments:
            a = int(s["start"] / STEP)
            b = max(int(s["end"] / STEP), a + 1)
            if a >= n:
                continue
            peak = float(self.db[a:min(b, n)].max()) - self.base
            if peak >= threshold_db:
                s["loud_db"] = round(peak, 1)

    def peak_windows(self, count: int, before: float = 120, after: float = 60) -> list[tuple[float, float]]:
        """Los `count` tramos con más reacción del stream, como (inicio, fin) en segundos."""
        if len(self.db) == 0:
            return []
        k = max(1, int(8 / STEP))  # suaviza ~8 s para encontrar momentos sostenidos, no clics sueltos
        smooth = np.convolve(self.db, np.ones(k) / k, mode="same")
        order = np.argsort(smooth)[::-1]
        picked: list[float] = []
        for i in order:
            t = i * STEP
            if all(abs(t - p) > before + after for p in picked):
                picked.append(t)
            if len(picked) >= count:
                break
        windows = [(max(0.0, t - before), min(self.duration, t + after)) for t in sorted(picked)]
        return windows
