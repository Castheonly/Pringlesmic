"""Publicación de Reels en Páginas de Facebook con la Graph API oficial.

Docs: https://developers.facebook.com/docs/video-api/guides/reels-publishing
"""
import os

import requests

VERSION = "v21.0"
GRAPH = f"https://graph.facebook.com/{VERSION}"


def upload(video_path, caption: str, page: dict) -> dict:
    page_id, token = page["page_id"], page["access_token"]

    r = requests.post(f"{GRAPH}/{page_id}/video_reels",
                      data={"upload_phase": "start", "access_token": token}, timeout=30)
    data = r.json()
    if "video_id" not in data:
        raise RuntimeError(f"Facebook start falló: {data}")
    video_id = data["video_id"]

    size = os.path.getsize(video_path)
    with open(video_path, "rb") as f:
        r = requests.post(
            f"https://rupload.facebook.com/video-upload/{VERSION}/{video_id}",
            headers={"Authorization": f"OAuth {token}", "offset": "0", "file_size": str(size)},
            data=f,
            timeout=600,
        )
    if not r.json().get("success"):
        raise RuntimeError(f"Facebook upload falló: {r.text[:300]}")

    r = requests.post(
        f"{GRAPH}/{page_id}/video_reels",
        data={
            "upload_phase": "finish",
            "video_id": video_id,
            "video_state": "PUBLISHED",
            "description": caption,
            "access_token": token,
        },
        timeout=60,
    )
    if not r.json().get("success"):
        raise RuntimeError(f"Facebook finish falló: {r.text[:300]}")
    return {"id": video_id, "status": "PUBLICADO", "url": f"https://www.facebook.com/reel/{video_id}"}
