"""Usa Claude para elegir los mejores momentos de la transcripción."""
import json

import anthropic

SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number", "description": "segundo de inicio"},
                    "end": {"type": "number", "description": "segundo de fin"},
                    "title": {"type": "string", "description": "gancho corto para mostrar en pantalla (máx 8 palabras)"},
                    "caption": {"type": "string", "description": "texto de la publicación (1-2 frases)"},
                    "hashtags": {"type": "array", "items": {"type": "string"}},
                    "score": {"type": "integer", "description": "potencial viral 1-10"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "title", "caption", "hashtags", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

SYSTEM = (
    "Eres editor de video experto en contenido corto vertical (TikTok, Reels). "
    "Recibes la transcripción con marcas de tiempo de un video largo y eliges los "
    "fragmentos con más potencial de viralizarse. Cada clip debe empezar al inicio de "
    "una frase y terminar en un cierre natural, sin cortar ideas a la mitad. "
    "Escribe títulos, captions y hashtags en el mismo idioma del video."
)


def _format_transcript(segments: list[dict]) -> str:
    return "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segments)


def pick_highlights(segments: list[dict], video_title: str, cfg: dict, limits: dict) -> list[dict]:
    client = anthropic.Anthropic()
    prompt = (
        f"Título del video: {video_title}\n\n"
        f"Elige los {limits['clips_per_video']} mejores clips. Cada uno debe durar entre "
        f"{limits['min_clip_seconds']} y {limits['max_clip_seconds']} segundos y no deben "
        f"solaparse. {cfg.get('extra_instructions', '')}\n\n"
        f"<transcripcion>\n{_format_transcript(segments)}\n</transcripcion>"
    )
    response = client.beta.messages.create(
        model=cfg.get("model", "claude-opus-5-5"),
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        output_config={
            "effort": cfg.get("effort", "medium"),
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        # Si el modelo rechaza la solicitud, la API reintenta con un modelo de respaldo.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        print("  ! Claude rechazó la solicitud; sin clips para este video")
        return []
    text = next(b.text for b in response.content if b.type == "text")
    clips = json.loads(text)["clips"]
    return _snap(clips, segments, limits)


def _snap(clips: list[dict], segments: list[dict], limits: dict) -> list[dict]:
    """Ajusta los cortes a los bordes de frase reales y valida duraciones."""
    starts = [s["start"] for s in segments]
    ends = [s["end"] for s in segments]
    good = []
    for c in sorted(clips, key=lambda c: -c["score"]):
        start = min(starts, key=lambda t: abs(t - c["start"]))
        end = min(ends, key=lambda t: abs(t - c["end"]))
        dur = end - start
        if dur < limits["min_clip_seconds"] - 3:
            continue
        if dur > limits["max_clip_seconds"] + 5:
            end = start + limits["max_clip_seconds"]
        if any(start < g["end"] and end > g["start"] for g in good):
            continue
        good.append({**c, "start": start, "end": end})
    return good[: limits["clips_per_video"]]
