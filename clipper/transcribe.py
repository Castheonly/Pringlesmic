"""Transcripción local con faster-whisper (corre en CPU, gratis)."""
from faster_whisper import WhisperModel


def transcribe(video_path, model_name: str = "small", language: str | None = None) -> list[dict]:
    """Devuelve segmentos [{start, end, text, words:[{start,end,word}]}]."""
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(
        str(video_path), language=language, word_timestamps=True, vad_filter=True
    )
    out = []
    for s in segments:
        out.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "words": [
                {"start": round(w.start, 2), "end": round(w.end, 2), "word": w.word.strip()}
                for w in (s.words or [])
            ],
        })
    return out
