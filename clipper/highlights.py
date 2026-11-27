"""Usa Claude para elegir los mejores momentos de la transcripción."""
import json
import os

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
                    "title": {"type": "string", "description": "gancho que se quema en el video los primeros segundos (máx 8 palabras)"},
                    "on_screen_text": {"type": "string",
                                       "description": "texto para que el usuario ponga en la app de TikTok (máx 12 palabras), enganchado a una tendencia o meme de la comunidad"},
                    "caption": {"type": "string", "description": "caption de la publicación: 1-2 frases + pregunta que provoque comentarios"},
                    "hashtags": {"type": "array", "items": {"type": "string"},
                                 "description": "4-7 hashtags: creador, comunidad, tendencia del momento y nicho"},
                    "sound_idea": {"type": "string", "description": "sonido/canción en tendencia que le quedaría, o vacío si el audio original es mejor"},
                    "trend": {"type": "string", "description": "tendencia, meme o tema del momento al que se engancha el clip"},
                    "score": {"type": "integer", "description": "potencial viral 1-10"},
                    "reason": {"type": "string"},
                },
                "required": ["start", "end", "title", "on_screen_text", "caption", "hashtags", "sound_idea", "trend", "score", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

SYSTEM = (
    "Eres el editor de una cuenta de clip farming de streamers latinos en TikTok y Facebook Reels. "
    "Tu objetivo es que cada clip sea viral: que enganche en el primer segundo, que la gente lo comparta "
    "y que la comunidad del creador comente. Recibes la transcripción con marcas de tiempo de un video "
    "o stream largo y eliges los fragmentos con más potencial. Busca: reacciones extremas, frases citables, "
    "polémicas y opiniones fuertes, momentos graciosos o incómodos, peleas o picantes con invitados, "
    "chismes, revelaciones y momentos que la comunidad va a reconocer (sus memes y bromas internas). "
    "Engancha cada clip a lo que está pasando: tendencias de TikTok, noticias del creador y temas del "
    "momento en redes. Escribe como la comunidad: español latino natural, con su jerga, sin sonar a marca "
    "ni a robot, sin inventar hechos que no estén en el clip. Nada de groserías en el título, el texto en "
    "pantalla, el caption ni los hashtags (el audio del clip las silencia). Cada clip debe empezar al inicio de "
    "una frase y terminar en un cierre natural, sin cortar ideas a la mitad. "
    "Las líneas marcadas con VOLUMEN ALTO indican gritos, risas o reacciones fuertes: "
    "son buenas candidatas, sobre todo si el clip arranca un poco antes para dar contexto. "
    "Escribe títulos, captions y hashtags en el mismo idioma del video."
)


def _format_transcript(segments: list[dict]) -> str:
    return "\n".join(
        f"[{s['start']:.1f}-{s['end']:.1f}]"
        + (f" (VOLUMEN ALTO +{s['loud_db']} dB)" if s.get("loud_db") else "")
        + f" {s['text']}"
        for s in segments
    )


def pick_highlights(segments: list[dict], video_title: str, cfg: dict, limits: dict, context: str = "") -> list[dict]:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("  · sin ANTHROPIC_API_KEY: elijo los clips por picos de reacción")
        return pick_by_loudness(segments, limits)
    client = anthropic.Anthropic()
    prompt = (
        f"Título del video: {video_title}\n\n"
        + (f"<contexto>\n{context}\n</contexto>\n\n" if context else "")
        + f"Elige los {limits['clips_per_video']} mejores clips. Cada uno debe durar entre "
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


def pick_by_loudness(segments: list[dict], limits: dict) -> list[dict]:
    """Modo gratis sin IA: arma clips alrededor de los momentos con más reacción (o más habla)."""
    lo, hi = limits["min_clip_seconds"], limits["max_clip_seconds"]

    def weight(s):
        return s.get("loud_db", 0) * 3 + len(s["text"].split()) / max(s["end"] - s["start"], 1)

    clips = []
    for i in sorted(range(len(segments)), key=lambda i: -weight(segments[i])):
        # arranca 1-2 frases antes del pico para dar contexto, y suma frases hasta la duración mínima
        a = max(0, i - 2)
        while a < i and segments[i]["end"] - segments[a]["start"] > hi:
            a += 1
        b = i
        while b + 1 < len(segments) and segments[b]["end"] - segments[a]["start"] < lo:
            b += 1
        start, end = segments[a]["start"], min(segments[b]["end"], segments[a]["start"] + hi)
        if end - start < lo - 3 or any(start < c["end"] and end > c["start"] for c in clips):
            continue
        text = segments[i]["text"]
        clips.append({
            "start": start, "end": end,
            "title": " ".join(text.split()[:7]),
            "caption": text[:200],
            "on_screen_text": " ".join(text.split()[:10]),
            "sound_idea": "",
            "trend": "",
            "hashtags": [],
            "score": min(10, 5 + int(segments[i].get("loud_db", 0) // 4)),
            "reason": "pico de reacción",
        })
        if len(clips) >= limits["clips_per_video"]:
            break
    return clips
