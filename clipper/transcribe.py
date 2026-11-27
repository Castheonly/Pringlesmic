"""Transcripción local con faster-whisper (corre en CPU, gratis)."""
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

_MODELS: dict = {}


def _model(name: str) -> WhisperModel:
    if name not in _MODELS:
        _MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODELS[name]


def _load_audio(path) -> np.ndarray:
    """Decodifica a 16 kHz mono con ffmpeg (evita depender de la versión de PyAV que trae faster-whisper)."""
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                          "-f", "f32le", "pipe:1"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def _run(model, path, language, offset: float = 0.0) -> list[dict]:
    audio = _load_audio(path)
    if audio.size == 0:
        return []
    segments, _ = model.transcribe(audio, language=language, word_timestamps=True, vad_filter=True)
    out = []
    for s in segments:
        out.append({
            "start": round(s.start + offset, 2),
            "end": round(s.end + offset, 2),
            "text": s.text.strip(),
            "words": [
                {"start": round(w.start + offset, 2), "end": round(w.end + offset, 2), "word": w.word.strip()}
                for w in (s.words or [])
            ],
        })
    return out


def transcribe(video_path, model_name: str = "small", language: str | None = None) -> list[dict]:
    """Transcribe el video completo. Devuelve [{start, end, text, words:[{start,end,word}]}]."""
    return _run(_model(model_name), video_path, language)


def transcribe_windows(video_path, windows, model_name: str = "small", language: str | None = None) -> list[dict]:
    """Transcribe solo algunos tramos (para streams largos). Los tiempos quedan relativos al video completo."""
    model, out = _model(model_name), []
    with tempfile.TemporaryDirectory() as tmp:
        for i, (a, b) in enumerate(windows):
            wav = Path(tmp) / f"w{i}.wav"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.2f}", "-i", str(video_path),
                            "-t", f"{b - a:.2f}", "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
            out.extend(_run(model, wav, language, offset=a))
    return out
