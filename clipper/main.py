"""Pipeline completo por campaña:
buscar videos nuevos -> detectar reacciones -> transcribir -> elegir clips -> renderizar -> publicar -> registrar links.
"""
import argparse
import copy
import json
import os
import re
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import yaml

from . import accounts, audio, highlights, render, sources, state, transcribe
from .publishers import facebook, tiktok

ROOT = Path(__file__).resolve().parent.parent
WORK, OUTPUT = ROOT / "work", ROOT / "output"
SUBMISSIONS = ROOT / "state" / "submissions.json"

# claves que una campaña puede sobrescribir directamente -> (sección, clave)
SHORTCUTS = {
    "language": ("transcription", "language"),
    "clips_per_video": ("limits", "clips_per_video"),
    "min_clip_seconds": ("limits", "min_clip_seconds"),
    "max_clip_seconds": ("limits", "max_clip_seconds"),
    "max_video_minutes": ("limits", "max_video_minutes"),
    "layout": ("render", "layout"),
    "subtitles": ("render", "subtitles"),
    "video_message": ("render", "video_message"),
    "branded_content": ("tiktok", "branded_content"),
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def campaign_config(defaults: dict, camp: dict) -> dict:
    cfg = _deep_merge(defaults, {k: v for k, v in camp.items() if isinstance(v, dict)})
    for key, (section, sub) in SHORTCUTS.items():
        if key in camp:
            target = cfg["publish"] if section == "tiktok" else cfg
            target.setdefault(section, {})[sub] = camp[key]
    if camp.get("rules"):
        cfg["highlights"]["extra_instructions"] = (
            cfg["highlights"].get("extra_instructions", "") + "\nReglas de la campaña: " + camp["rules"])
    if "publish" in camp and isinstance(camp["publish"], bool):
        cfg["publish"]["enabled"] = camp["publish"]
    return cfg


def load_config(path: Path) -> tuple[dict, list[dict]]:
    raw = yaml.safe_load(path.read_text())
    defaults = raw.get("defaults", raw)
    camps = raw.get("campaigns") or [{"name": "default", "sources": raw.get("sources", [])}]
    return defaults, camps


ACCOUNTS: dict = {"tiktok": [], "facebook": []}


def _caption(clip: dict, camp: dict) -> str:
    tags = list(dict.fromkeys(
        ["#" + re.sub(r"[^\w]", "", h.lstrip("#")) for h in clip.get("hashtags", [])]
        + ["#" + re.sub(r"[^\w]", "", h.lstrip("#")) for h in camp.get("required_hashtags", [])]
    ))
    parts = [clip["caption"], camp.get("caption_suffix", ""), " ".join(tags)]
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def _wanted(accounts: list[dict], names: list | None) -> list[dict]:
    return accounts if not names else [a for a in accounts if a.get("name") in names]


def publish(path: Path, caption: str, cfg: dict, camp: dict) -> list[dict]:
    posts = []
    targets = []
    allowed = camp.get("platforms") or ["tiktok", "facebook"]
    if cfg["tiktok"].get("enabled") and "tiktok" in allowed:
        for acc in _wanted(ACCOUNTS["tiktok"], camp.get("tiktok_accounts")):
            targets.append(("tiktok", acc.get("name", "?"), lambda a=acc: tiktok.upload(path, caption, a, cfg["tiktok"])))
    if cfg["facebook"].get("enabled") and "facebook" in allowed:
        for page in _wanted(ACCOUNTS["facebook"], camp.get("facebook_pages")):
            targets.append(("facebook", page.get("name", page.get("page_id")), lambda p=page: facebook.upload(path, caption, p)))
    for platform, account, fn in targets:
        try:
            res = fn()
            print(f"    ✓ {platform}:{account} {res.get('status')} {res.get('url') or res.get('id')}")
        except Exception as e:
            res = {"status": "ERROR", "error": str(e)[:300]}
            print(f"    ✗ {platform}:{account}: {e}")
        posts.append({"platform": platform, "account": account, **res})
    return posts


def record_submission(entry: dict) -> None:
    data = json.loads(SUBMISSIONS.read_text()) if SUBMISSIONS.exists() else []
    data.append(entry)
    SUBMISSIONS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def summary(line: str) -> None:
    """Escribe en el resumen de la corrida de GitHub Actions (visible en la pestaña Actions)."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a") as f:
            f.write(line + "\n")


def process_video(video: dict, camp: dict, cfg: dict, do_publish: bool, st: dict) -> None:
    name = camp["name"]
    print(f"\n▶ [{name}] {video['title']} ({video['id']})")
    src = sources.download(video, WORK, cfg["limits"].get("download_max_height", 1080))
    loud = audio.Loudness(src)
    tcfg, lim = cfg["transcription"], cfg["limits"]

    if loud.duration > lim.get("max_full_transcribe_minutes", 45) * 60:
        windows = loud.peak_windows(lim.get("long_stream_windows", 8))
        print(f"  · video largo ({loud.duration / 60:.0f} min): transcribo solo {len(windows)} tramos con más reacción")
        segs = transcribe.transcribe_windows(src, windows, tcfg["model"], tcfg.get("language"))
    else:
        print("  · transcribiendo…")
        segs = transcribe.transcribe(src, tcfg["model"], tcfg.get("language"))
    loud.annotate(segs)

    if not segs:
        state.mark(st, f"{name}::{video['id']}", {"campaign": name, "title": video["title"], "clips": [], "note": "sin voz"})
        src.unlink(missing_ok=True)
        return
    n_loud = sum(1 for s in segs if s.get("loud_db"))
    print(f"  · {len(segs)} segmentos ({n_loud} con reacción fuerte); pidiendo a Claude los mejores momentos…")
    clips = highlights.pick_highlights(segs, video["title"], cfg["highlights"], lim)

    done = []
    for i, clip in enumerate(clips, 1):
        out = OUTPUT / name / video["id"] / f"clip_{i:02d}.mp4"
        print(f"  · clip {i}: {clip['start']:.0f}s-{clip['end']:.0f}s  «{clip['title']}» (score {clip['score']})")
        render.render_clip(src, out, clip, segs, cfg["render"])
        caption = _caption(clip, camp)
        out.with_suffix(".txt").write_text(caption, encoding="utf-8")
        posts = publish(out, caption, cfg["publish"], camp) if do_publish else []
        entry = {
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "campaign": name,
            "source_title": video["title"],
            "source_url": video["url"],
            "start": clip["start"], "end": clip["end"],
            "title": clip["title"], "score": clip["score"],
            "caption": caption,
            "file": str(out.relative_to(ROOT)),
            "posts": posts,
        }
        record_submission(entry)
        links = ", ".join(p.get("url") or p.get("status", "") for p in posts) or "(sin publicar)"
        summary(f"| {name} | {clip['title']} | {clip['score']} | {links} |")
        done.append({k: clip[k] for k in ("start", "end", "title", "score")})
        if do_publish and i < len(clips):
            time.sleep(cfg["publish"].get("delay_between_posts_seconds", 0))

    state.mark(st, f"{name}::{video['id']}", {"campaign": name, "title": video["title"], "clips": done})
    src.unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--url", help="procesar solo este video/canal")
    ap.add_argument("--campaign", help="campaña a usar (reglas, hashtags, cuentas)")
    ap.add_argument("--no-publish", action="store_true", help="solo generar los clips")
    args = ap.parse_args()

    defaults, camps = load_config(Path(args.config))
    if args.campaign:
        camps = [c for c in camps if c["name"] == args.campaign] or [{"name": args.campaign}]
    if args.url:
        camps = [{**camps[0], "enabled": True, "sources": [{"url": args.url, "max_new_videos": 1}]}]

    ACCOUNTS.update(accounts.load())
    print(f"Cuentas: {len(ACCOUNTS['tiktok'])} TikTok, {len(ACCOUNTS['facebook'])} Facebook")
    st = state.load()
    summary("| Campaña | Clip | Score | Publicado |\n|---|---|---|---|")
    failures = 0
    for camp in camps:
        if not camp.get("enabled", True):
            continue
        if camp.get("ends") and str(camp["ends"]) < datetime.now(timezone.utc).date().isoformat():
            print(f"[{camp['name']}] campaña terminada ({camp['ends']}), la salto")
            continue
        cfg = campaign_config(defaults, camp)
        do_publish = cfg["publish"].get("enabled", False) and not args.no_publish
        done_ids = {k.split("::", 1)[1] for k in st if k.startswith(camp["name"] + "::")}
        for s in camp.get("sources", []):
            print(f"[{camp['name']}] buscando videos nuevos en {s['url']}")
            try:
                videos = sources.list_new_videos(s["url"], done_ids, s.get("max_new_videos", 1),
                                                 cfg["limits"]["max_video_minutes"])
            except Exception as e:
                print(f"  ✗ no se pudo leer la fuente: {e}")
                failures += 1
                continue
            if not videos:
                print("  (nada nuevo)")
            for v in videos:
                try:
                    process_video(v, camp, cfg, do_publish, st)
                except Exception:
                    failures += 1
                    traceback.print_exc()
    if any(a.pop("_dirty", False) for a in ACCOUNTS["tiktok"]):
        try:
            accounts.save(ACCOUNTS)
        except Exception as e:
            print(f"! No pude guardar los tokens renovados: {e}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
