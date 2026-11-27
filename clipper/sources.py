"""Descubre y descarga videos nuevos con yt-dlp.

Funciona con YouTube, Twitch (VODs), Kick, TikTok, X, Facebook y +1000 sitios más.
"""
import os
from pathlib import Path

import yt_dlp


def _base_opts() -> dict:
    opts = {"quiet": True, "no_warnings": True}
    cookies = os.environ.get("YT_COOKIES_FILE")
    if cookies and Path(cookies).exists():
        opts["cookiefile"] = cookies
    return opts


def list_new_videos(url: str, processed, max_new: int, max_minutes: int) -> list[dict]:
    """Devuelve hasta `max_new` videos de `url` que aún no se procesaron."""
    opts = {**_base_opts(), "extract_flat": "in_playlist", "playlistend": 25}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    entries = info.get("entries") or [info]
    found = []
    for e in entries:
        vid = e.get("id")
        if not vid or vid in processed:
            continue
        dur = e.get("duration")
        if dur and dur > max_minutes * 60:
            print(f"  - salto {vid}: dura {dur // 60} min (> {max_minutes})")
            continue
        if e.get("live_status") in ("is_live", "is_upcoming"):
            continue
        found.append({
            "id": vid,
            "title": e.get("title") or vid,
            "url": e.get("webpage_url") or (e.get("url") if str(e.get("url", "")).startswith("http") else None)
                   or f"https://www.youtube.com/watch?v={vid}",
        })
        if len(found) >= max_new:
            break
    return found


def download(video: dict, workdir: Path, max_height: int = 1080) -> Path:
    workdir.mkdir(parents=True, exist_ok=True)
    opts = {
        **_base_opts(),
        "format": f"bv*[height<={max_height}][ext=mp4]+ba[ext=m4a]/bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "merge_output_format": "mp4",
        "outtmpl": str(workdir / f"{video['id']}.%(ext)s"),
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        ydl.download([video["url"]])
    path = workdir / f"{video['id']}.mp4"
    if not path.exists():
        matches = list(workdir.glob(f"{video['id']}.*"))
        if not matches:
            raise RuntimeError(f"No se descargó {video['id']}")
        path = matches[0]
    return path
