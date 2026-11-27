"""Descubre y descarga videos con yt-dlp.

Funciona con Kick (VODs de un canal), YouTube (videos y directos pasados), Twitch, TikTok, X y +1000 sitios.
Descarga en dos pasos para streams largos:
  1) una versión liviana (baja calidad) para analizar volumen y transcribir;
  2) solo los tramos de los clips elegidos en alta calidad.
"""
import os
import re
from pathlib import Path

import yt_dlp
from yt_dlp.utils import download_range_func

KICK_CHANNEL = re.compile(r"^https?://(?:www\.)?kick\.com/([\w-]+)/?(?:[?#].*)?$")
YT_CHANNEL = re.compile(r"^https?://(?:www\.)?youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w.-]+)/?(?:[?#].*)?$")


def _base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True, "noprogress": True, "enable_file_urls": True}
    cookies = os.environ.get("YT_COOKIES_FILE")
    if cookies and Path(cookies).exists():
        opts["cookiefile"] = cookies
    return opts


YT_BLOCK_HELP = ("YouTube bloqueó la descarga desde GitHub. Solución: agrega el secret YT_COOKIES con las cookies de "
                 "una cuenta de YouTube (ver GUIA.md, sección 'Si algo falla').")


def friendly(e: Exception) -> str:
    msg = str(e)
    if "confirm you" in msg and "bot" in msg:
        return YT_BLOCK_HELP
    return msg[:300]


def expand_source(url: str) -> list[str]:
    """Convierte la URL de un canal en las listas de videos que hay que revisar."""
    url = url.strip()
    m = KICK_CHANNEL.match(url)
    if m and m.group(1) not in ("video", "categories", "search", "auth"):
        return [f"https://kick.com/{m.group(1)}/videos"]  # VODs, nunca el directo en vivo
    m = YT_CHANNEL.match(url)
    if m:
        base = f"https://www.youtube.com/{m.group(1)}"
        return [f"{base}/videos", f"{base}/streams"]
    return [url]


def list_new_videos(url: str, processed, max_new: int, max_minutes: int) -> list[dict]:
    """Devuelve hasta `max_new` videos de la fuente que aún no se procesaron (los más nuevos primero)."""
    found = []
    for listing in expand_source(url):
        if len(found) >= max_new:
            break
        opts = {**_base_opts(), "extract_flat": "in_playlist", "playlistend": 15}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(listing, download=False)
        except yt_dlp.utils.DownloadError as e:
            if listing.endswith("/streams"):   # canal sin directos pasados
                continue
            raise e
        for e in info.get("entries") or [info]:
            vid = e.get("id")
            if not vid or vid in processed or any(f["id"] == vid for f in found):
                continue
            if e.get("live_status") in ("is_live", "is_upcoming") or e.get("availability") not in (None, "public"):
                continue
            dur = e.get("duration")
            if dur and dur > max_minutes * 60:
                print(f"  - salto {vid}: dura {int(dur) // 60} min (> {max_minutes})")
                continue
            web = e.get("webpage_url") or e.get("url")
            if not str(web or "").startswith(("http", "file:")):
                web = f"https://www.youtube.com/watch?v={vid}"
            found.append({"id": vid, "title": e.get("title") or vid, "url": web,
                          "channel": e.get("channel") or e.get("uploader") or info.get("title"),
                          "timestamp": e.get("timestamp") or e.get("release_timestamp")})
            if len(found) >= max_new:
                break
    return found


def _find(workdir: Path, stem: str) -> Path:
    for ext in ("mp4", "mkv", "webm", "m4a"):
        p = workdir / f"{stem}.{ext}"
        if p.exists():
            return p
    matches = [m for m in workdir.glob(f"{stem}.*") if not m.name.endswith((".part", ".ytdl"))]
    if not matches:
        raise RuntimeError(f"No se descargó {stem}")
    return matches[0]


def download_preview(video: dict, workdir: Path, max_height: int = 360) -> Path:
    """Versión liviana del video completo (para analizar). En streams de horas pesa poco."""
    workdir.mkdir(parents=True, exist_ok=True)
    stem = f"{_safe(video['id'])}_preview"
    opts = {
        **_base_opts(),
        "format": f"b[height<={max_height}]/bv*[height<={max_height}]+ba/worst",
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / f"{stem}.%(ext)s"),
        "concurrent_fragment_downloads": 8,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([video["url"]])
    return _find(workdir, stem)


def download_section(video: dict, workdir: Path, start: float, end: float, idx: int,
                     max_height: int = 1080) -> Path:
    """Descarga solo el tramo [start, end] en alta calidad."""
    stem = f"{_safe(video['id'])}_hq{idx:02d}"
    opts = {
        **_base_opts(),
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / f"{stem}.%(ext)s"),
        "download_ranges": download_range_func(None, [(max(0.0, start), end)]),
        "force_keyframes_at_cuts": True,
        "concurrent_fragment_downloads": 8,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([video["url"]])
    return _find(workdir, stem)


def _safe(s: str) -> str:
    return re.sub(r"[^\w-]", "_", s)[:80]
