"""Pipeline completo: buscar videos nuevos -> transcribir -> elegir clips -> renderizar -> publicar."""
import argparse
import json
import os
import re
import time
import traceback
from pathlib import Path

import yaml

from . import audio, highlights, render, sources, state, transcribe
from .publishers import facebook, tiktok

ROOT = Path(__file__).resolve().parent.parent
WORK, OUTPUT = ROOT / "work", ROOT / "output"


def _accounts(env_name: str) -> list[dict]:
    raw = os.environ.get(env_name, "").strip()
    return json.loads(raw) if raw else []


def _caption(clip: dict) -> str:
    tags = " ".join("#" + re.sub(r"[^\w]", "", h.lstrip("#")) for h in clip.get("hashtags", []))
    return f"{clip['caption']}\n\n{tags}".strip()


def publish(path: Path, clip: dict, cfg: dict) -> dict:
    results, caption = {}, _caption(clip)
    if cfg["tiktok"].get("enabled"):
        for acc in _accounts("TIKTOK_ACCOUNTS_JSON"):
            key = f"tiktok:{acc.get('name', '?')}"
            try:
                results[key] = tiktok.upload(path, caption, acc, cfg["tiktok"])
                print(f"    ✓ {key}: {results[key]}")
            except Exception as e:
                results[key] = f"ERROR: {e}"
                print(f"    ✗ {key}: {e}")
    if cfg["facebook"].get("enabled"):
        for page in _accounts("FACEBOOK_PAGES_JSON"):
            key = f"facebook:{page.get('name', page.get('page_id'))}"
            try:
                results[key] = facebook.upload(path, caption, page)
                print(f"    ✓ {key}: {results[key]}")
            except Exception as e:
                results[key] = f"ERROR: {e}"
                print(f"    ✗ {key}: {e}")
    return results


def process_video(video: dict, cfg: dict, do_publish: bool, st: dict) -> None:
    print(f"\n▶ {video['title']} ({video['id']})")
    src = sources.download(video, WORK)
    print("  · transcribiendo…")
    segs = transcribe.transcribe(src, cfg["transcription"]["model"], cfg["transcription"].get("language"))
    if not segs:
        state.mark(st, video["id"], {"title": video["title"], "clips": [], "note": "sin voz"})
        return
    audio.annotate_loudness(src, segs)
    print(f"  · {len(segs)} segmentos ({sum(1 for s in segs if s.get('loud_db'))} con reacción fuerte); pidiendo a Claude los mejores momentos…")
    clips = highlights.pick_highlights(segs, video["title"], cfg["highlights"], cfg["limits"])

    done = []
    for i, clip in enumerate(clips, 1):
        out = OUTPUT / video["id"] / f"clip_{i:02d}.mp4"
        print(f"  · clip {i}: {clip['start']:.0f}s-{clip['end']:.0f}s  «{clip['title']}» (score {clip['score']})")
        render.render_clip(src, out, clip, segs, cfg["render"])
        (out.with_suffix(".txt")).write_text(_caption(clip), encoding="utf-8")
        entry = {k: clip[k] for k in ("start", "end", "title", "score")}
        if do_publish:
            entry["published"] = publish(out, clip, cfg["publish"])
            time.sleep(cfg["publish"].get("delay_between_posts_seconds", 0))
        done.append(entry)

    state.mark(st, video["id"], {"title": video["title"], "clips": done})
    src.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--url", help="procesar solo este video/canal (ignora sources del config)")
    ap.add_argument("--no-publish", action="store_true", help="solo generar los clips")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    do_publish = cfg["publish"].get("enabled", False) and not args.no_publish
    st = state.load()
    srcs = [{"url": args.url, "max_new_videos": 1}] if args.url else cfg["sources"]

    failures = 0
    for s in srcs:
        print(f"Buscando videos nuevos en {s['url']}")
        try:
            videos = sources.list_new_videos(s["url"], st, s.get("max_new_videos", 1),
                                             cfg["limits"]["max_video_minutes"])
        except Exception as e:
            print(f"  ✗ no se pudo leer la fuente: {e}")
            failures += 1
            continue
        if not videos:
            print("  (nada nuevo)")
        for v in videos:
            try:
                process_video(v, cfg, do_publish, st)
            except Exception:
                failures += 1
                traceback.print_exc()
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
