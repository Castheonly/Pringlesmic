"""Detecta groserías (español latino/España + inglés) para silenciarlas en el audio y taparlas en los subtítulos.

Se usa el tiempo exacto de cada palabra que da Whisper. Puedes agregar palabras propias en
config.yaml -> defaults.render.profanity_extra.
"""
import re
import unicodedata

# raíces/prefijos: una palabra que EMPIEZA con alguno de estos se considera grosería
PREFIXES = [
    # español
    "hijueput", "hijuept", "jueput", "juepucha", "hp", "hpta", "gonorre", "malparid", "piroba", "pirobo",
    "puta", "puto", "putica", "putic", "putisim", "puteri", "putear", "pute",
    "verga", "vergaz", "vergot", "mierd", "carajo", "cabron", "cabrón", "chinga", "chingu",
    "chingad", "culer", "culia", "culiao", "pendej", "maric", "maricon", "marico", "mamaguev", "mamahuev",
    "mamagüev", "mamabich", "huevon", "guevon", "webon", "weon", "gilipoll", "joder", "jodid", "polla",
    "follar", "follad", "cojon", "concha", "conchetumare", "conchesumadre", "csm", "ctm", "pinga", "pingon",
    "carechimba", "malnacid", "perra", "zorra", "bicho", "culo", "ojete",
    "mamon", "mamona", "chucha", "chuchamadre", "berga", "cagad", "cagar", "cago", "mmg", "mamaguebo",
    # inglés
    "fuck", "fck", "fuk", "motherfuck", "shit", "bitch", "bastard", "asshole", "dick", "pussy", "cunt",
    "nigg", "fag", "whore", "slut",
]
# palabras exactas (cortas o que como prefijo darían falsos positivos)
EXACT = {"hp", "hpta", "csm", "ctm", "mmg", "ass", "cono", "verg", "vergas"}
# palabras normales que empiezan igual que una grosería
SAFE = {"computa", "computador", "computadora", "disputa", "reputacion", "imputado", "conchas",
        "perrazo", "pendiente", "pendientes", "cagatinta", "dickens", "shiitake", "culto",
        "cultura", "cultural", "culturales", "culpa", "culpable", "cultivo", "culminar", "perrito", "perritos",
        "perro", "perros", "bichos", "estupidez"}


def _norm(word: str) -> str:
    w = unicodedata.normalize("NFKD", word.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", w)


def is_profane(word: str, extra: list[str] | None = None) -> bool:
    w = _norm(word)
    if not w or w in SAFE:
        return False
    if w in EXACT:
        return True
    prefixes = PREFIXES + [_norm(x) for x in (extra or [])]
    return any(len(p) >= 3 and w.startswith(_norm(p)) for p in prefixes) or w in {_norm(x) for x in (extra or [])}


def censor(word: str) -> str:
    """'mierda' -> 'm****' (mantiene signos de puntuación alrededor)."""
    m = re.match(r"^(\W*)(\w)(\w*)(\W*)$", word, flags=re.UNICODE)
    if not m:
        return "*" * len(word)
    return f"{m.group(1)}{m.group(2)}{'*' * max(3, len(m.group(3)))}{m.group(4)}"


def mute_ranges(segments: list[dict], start: float, end: float, extra=None, pad: float = 0.08) -> list[tuple[float, float]]:
    """Tramos (relativos al inicio del clip) donde hay que silenciar el audio."""
    out = []
    for s in segments:
        for w in s.get("words", []):
            if w["end"] <= start or w["start"] >= end or not is_profane(w["word"], extra):
                continue
            a, b = max(0.0, w["start"] - start - pad), min(end - start, w["end"] - start + pad)
            if out and a <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
    return out


def audio_filter(ranges: list[tuple[float, float]]) -> str | None:
    if not ranges:
        return None
    cond = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in ranges)
    return f"volume=enable='{cond}':volume=0"
