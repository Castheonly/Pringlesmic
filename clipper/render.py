"""Corta el clip, lo pasa a vertical 9:16 y le quema subtítulos animados con ffmpeg.

Layouts:
  blur  - video completo al centro con fondo difuminado
  crop  - recorte fijo al centro
  face  - recorte que sigue la cara (OpenCV) con movimiento de cámara suave
  split - facecam arriba + gameplay abajo (ideal para streams/VODs de juegos)
"""
import subprocess
from pathlib import Path

import cv2

from . import tracking

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
    align, margin_v = cfg.get("_align", 2), cfg.get("_margin_v", 560)
    n = max(1, int(cfg.get("words_per_caption", 3)))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Cap,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,2,{align},60,60,{margin_v},1",
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


ENCODE = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart"]


def _run(cmd, cwd=None, stdin=None):
    return subprocess.run(cmd, check=True, cwd=cwd, input=stdin)


def render_clip(src: Path, out: Path, clip: dict, segments: list[dict], cfg: dict) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    start, end = clip["start"], clip["end"]
    layout = cfg.get("layout", "blur")
    ass_path = out.with_suffix(".ass")

    if layout in ("face", "split"):
        # 1) cortar el fragmento a un archivo temporal (30 fps, máx 1080p)
        tmp = out.with_name(out.stem + "_src.mp4")
        _run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start:.2f}", "-i", str(src.resolve()),
              "-t", f"{end - start:.2f}", "-vf", "scale=-2:'min(1080,ih)',fps=30",
              "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-c:a", "aac", str(tmp.resolve())])
        print(f"    · seguimiento facial ({layout})…")
        try:
            ok = _render_tracked(tmp, out, ass_path, clip, segments, cfg, layout)
        finally:
            tmp.unlink(missing_ok=True)
        if ok:
            return out
        print("    · no se detectaron caras; uso layout blur")
        layout = "blur"

    ass_path.write_text(build_ass(segments, start, end, clip.get("title", ""), cfg), encoding="utf-8")
    if layout == "crop":
        vf = f"[0:v]scale=-2:{H},crop={W}:{H}[base]"
    else:
        vf = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=25:5[bg];"
              f"[0:v]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[base]")
    vf += f";[base]subtitles={ass_path.name}[v]"
    _run(["ffmpeg", "-y", "-loglevel", "error",
          "-ss", f"{start:.2f}", "-i", str(src.resolve()), "-t", f"{end - start:.2f}",
          "-filter_complex", vf, "-map", "[v]", "-map", "0:a?", "-r", "30", *ENCODE, str(out.resolve())],
         cwd=ass_path.parent)
    return out


def _crop(frame, cx, cy, cw, ch):
    """Recorta un rectángulo cw x ch centrado en (cx, cy), sin salirse del frame."""
    fh, fw = frame.shape[:2]
    cw, ch = min(int(cw), fw), min(int(ch), fh)
    x = int(min(max(cx - cw / 2, 0), fw - cw))
    y = int(min(max(cy - ch / 2, 0), fh - ch))
    return frame[y:y + ch, x:x + cw]


def _render_tracked(tmp: Path, out: Path, ass_path: Path, clip, segments, cfg, layout) -> bool:
    dets, fps, n = tracking.track(tmp)
    cap = cv2.VideoCapture(str(tmp))
    fw, fh = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    if layout == "face":
        path = tracking.smooth_path(dets, n, fw)
        if path is None:
            cap.release()
            return False
        sub_cfg = cfg
    else:
        cam = tracking.facecam_box(dets)
        if cam is None:
            cap.release()
            return False
        fcx, fcy, face_h = cam
        zoom = cfg.get("split_face_zoom", 3.2)       # alto del recorte = alto de la cara * zoom
        top_h = int(H * cfg.get("split_top_ratio", 0.45))
        bot_h = H - top_h
        sub_cfg = {**cfg, "_align": 8, "_margin_v": top_h - cfg.get("font_size", 80) // 2}

    ass_path.write_text(build_ass(segments, clip["start"], clip["end"], clip.get("title", ""), sub_cfg),
                        encoding="utf-8")
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", f"{fps}", "-i", "pipe:0",
         "-i", str(tmp.resolve()),
         "-filter_complex", f"[0:v]subtitles={ass_path.name}[v]", "-map", "[v]", "-map", "1:a?",
         *ENCODE, "-shortest", str(out.resolve())],
        stdin=subprocess.PIPE, cwd=ass_path.parent)
    f = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if layout == "face":
            canvas = cv2.resize(_crop(frame, path[min(f, n - 1)], fh / 2, fh * W / H, fh), (W, H))
        else:
            ch = face_h * zoom
            top = cv2.resize(_crop(frame, fcx, fcy, ch * W / top_h, ch), (W, top_h))
            game = cv2.resize(_crop(frame, fw / 2, fh / 2, fh * W / bot_h, fh), (W, bot_h))
            canvas = cv2.vconcat([top, game])
        ff.stdin.write(canvas.tobytes())
        f += 1
    cap.release()
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg falló al codificar el clip con seguimiento")
    return True
