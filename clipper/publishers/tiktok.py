"""Publicación en TikTok con la Content Posting API oficial.

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started
"""
import math
import os
import time

import requests

API = "https://open.tiktokapis.com/v2"
CHUNK = 10 * 1024 * 1024


def get_access_token(refresh_token: str) -> dict:
    r = requests.post(
        f"{API}/oauth/token/",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": os.environ["TIKTOK_CLIENT_KEY"],
            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"TikTok no devolvió access_token: {data}")
    return data


def upload(video_path, caption: str, account: dict, cfg: dict) -> str:
    token = get_access_token(account["refresh_token"])["access_token"]
    size = os.path.getsize(video_path)
    chunk = size if size <= CHUNK else CHUNK
    total = 1 if size <= CHUNK else size // CHUNK  # el último chunk absorbe el resto
    source = {"source": "FILE_UPLOAD", "video_size": size, "chunk_size": chunk, "total_chunk_count": total}

    if cfg.get("mode", "inbox") == "direct":
        url = f"{API}/post/publish/video/init/"
        body = {
            "post_info": {
                "title": caption[:2200],
                "privacy_level": cfg.get("privacy_level", "SELF_ONLY"),
                "disable_comment": False,
                "disable_duet": False,
                "disable_stitch": False,
            },
            "source_info": source,
        }
    else:
        url = f"{API}/post/publish/inbox/video/init/"
        body = {"source_info": source}

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    r = requests.post(url, json=body, headers=headers, timeout=30)
    data = r.json()
    if r.status_code != 200 or data.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"TikTok init falló: {data}")
    publish_id, upload_url = data["data"]["publish_id"], data["data"]["upload_url"]

    with open(video_path, "rb") as f:
        for i in range(total):
            begin = i * chunk
            length = (size - begin) if i == total - 1 else chunk
            piece = f.read(length)
            rr = requests.put(
                upload_url,
                data=piece,
                headers={
                    "Content-Type": "video/mp4",
                    "Content-Length": str(len(piece)),
                    "Content-Range": f"bytes {begin}-{begin + len(piece) - 1}/{size}",
                },
                timeout=300,
            )
            if rr.status_code not in (200, 201, 206):
                raise RuntimeError(f"TikTok upload chunk {i} falló: {rr.status_code} {rr.text[:300]}")

    return _wait_status(publish_id, headers)


def _wait_status(publish_id: str, headers: dict) -> str:
    for _ in range(20):
        time.sleep(6)
        r = requests.post(f"{API}/post/publish/status/fetch/", json={"publish_id": publish_id},
                          headers=headers, timeout=30)
        status = r.json().get("data", {}).get("status", "")
        if status in ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX"):
            return f"{publish_id} ({status})"
        if status == "FAILED":
            raise RuntimeError(f"TikTok procesamiento falló: {r.json()}")
    return f"{publish_id} (procesando)"
