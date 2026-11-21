"""Corta el clip, lo pasa a vertical 9:16 y le quema subtítulos animados con ffmpeg."""
import subprocess
from pathlib import Path

W, H = 1080, 1920


def _ts(t: float) -> str:
    t = max(t, 0)
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def _escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(segments: list[dict], start: float, end: float, title: str, cfg: dict) -> str:
    font, size = cfg.get("font", "Arial"), cfg.get("font_size", 80)
    hl = cfg.get("highlight_color", "&H0000FFFF")
    n = max(1, int(cfg.get("words_per_caption", 3)))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,2,60,60,560,1",
        f"Style: Title,{font},{int(size * 0.8)},&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,80,80,220,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    title_secs = cfg.get("show_title_seconds", 0)
    if title and title_secs:
        lines.append(f"Dialogue: 1,{_ts(0)},{_ts(title_secs)},Title,,0,0,0,,{_escape(title.upper())}")

    if cfg.get("subtitles", True):
        words = [w for s in segments for w in s.get("words", []) if w["end"] > start and w["start"] < end]
        for i in range(0, len(words), n):
            chunk = words[i:i + n]
            for j, w in enumerate(chunk):
                t0 = w["start"] - start
                t1 = (chunk[j + 1]["start"] if j + 1 < len(chunk) else chunk[-1]["end"]) - start
                parts = [
                    (f"{{\\c{hl}}}{_escape(x['word'])}{{\\c&H00FFFFFF&}}" if k == j else _escape(x["word"]))
                    for k, x in enumerate(chunk)
                ]
                lines.append(f"Dialogue: 0,{_ts(t0)},{_ts(max(t1, t0 + 0.05))},Cap,,0,0,0,,{' '.join(parts).upper()}")
    return "\n".join(lines) + "\n"


def render_clip(src: Path, out: Path, clip: dict, segments: list[dict], cfg: dict) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    start, end = clip["start"], clip["end"]
    ass_path = out.with_suffix(".ass")
    ass_path.write_text(build_ass(segments, start, end, clip.get("title", ""), cfg), encoding="utf-8")

    if cfg.get("layout", "blur") == "crop":
        vf = f"[0:v]scale=-2:{H},crop={W}:{H}[base]"
    else:
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:5[bg];"
              f"[0:v]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    vf += f";[base]subtitles={ass_path.name}[v]"

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", f"{start:.2f}", "-i", str(src.resolve()), "-t", f"{end - start:.2f}",
        "-filter_complex", vf, "-map", "[v]", "-map", "0:a?",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        str(out.resolve()),
    ]
    subprocess.run(cmd, check=True, cwd=ass_path.parent)
    return out
