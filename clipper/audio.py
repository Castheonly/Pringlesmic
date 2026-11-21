"""Detecta picos de volumen (gritos, risas, explosiones) para encontrar reacciones."""
import subprocess

import numpy as np

RATE = 8000


def annotate_loudness(video_path, segments: list[dict], threshold_db: float = 6.0) -> None:
    """Agrega a cada segmento `loud_db`: cuántos dB está su pico sobre el volumen típico del video."""
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(video_path), "-vn", "-ac", "1", "-ar", str(RATE),
         "-f", "s16le", "pipe:1"],
        check=True, capture_output=True,
    ).stdout
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if pcm.size == 0:
        return
    win = RATE // 2  # ventanas de 0,5 s
    n = pcm.size // win
    rms = np.sqrt(np.mean(pcm[: n * win].reshape(n, win) ** 2, axis=1)) + 1e-6
    db = 20 * np.log10(rms)
    base = float(np.median(db))
    for s in segments:
        a, b = int(s["start"] * 2), max(int(s["end"] * 2), int(s["start"] * 2) + 1)
        if a >= n:
            continue
        peak = float(db[a:min(b, n)].max()) - base
        if peak >= threshold_db:
            s["loud_db"] = round(peak, 1)
