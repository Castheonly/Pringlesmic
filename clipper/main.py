"""Pipeline de clipping en 3 fases (en GitHub Actions corren en paralelo):

  plan     -> busca videos nuevos en todas las campañas y arma la lista de trabajos
  clip     -> procesa UN video: preview liviano, reacciones, transcripción, Claude elige clips,
              descarga solo esos tramos en HD, formato vertical + subtítulos  (uno por máquina)
  publish  -> junta los clips de todas las máquinas, publica en TikTok/Facebook y guarda el registro

Sin argumentos corre las 3 fases seguidas (uso local).
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

from . import highlights, sources, state, trends
# audio/render/transcribe (video) y accounts/publishers (cifrado) se importan solo en la fase que los usa,
# así cada máquina instala lo mínimo.

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
    from .publishers import facebook, tiktok
    posts, targets = [], []
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


def _camp(camps: list[dict], name: str) -> dict:
    return next((c for c in camps if c["name"] == name), {"name": name})


# ------------------------------------------------------------------ plan
def plan(defaults: dict, camps: list[dict], url: str | None = None, campaign: str | None = None) -> list[dict]:
    st = state.load()
    if url:
        camp = _camp(camps, campaign or "videos-sueltos")
        found = sources.list_new_videos(url, set(), 1, 100000)
        return [{"campaign": camp["name"], "video": v} for v in found]

    try:
        trends.refresh(camps, defaults.get("trends", {}))
    except Exception as e:
        print(f"! Radar de tendencias falló (sigo igual): {e}")

    limit = defaults["limits"].get("max_videos_per_run", 12)
    jobs, today = [], datetime.now(timezone.utc).date().isoformat()
    for camp in camps:
        if not camp.get("enabled", True):
            continue
        if campaign and camp["name"] != campaign:
            continue
        if camp.get("ends") and str(camp["ends"]) < today:
            print(f"[{camp['name']}] campaña terminada ({camp['ends']}), la salto")
            continue
        cfg = campaign_config(defaults, camp)
        prefix = camp["name"] + "::"
        skip = {k.split("::", 1)[1] for k, v in st.items() if k.startswith(prefix)
                and (v.get("clips") is not None or v.get("attempts", 0) >= 3)}
        for s in camp.get("sources", []):
            try:
                videos = sources.list_new_videos(s["url"], skip, s.get("max_new_videos", 1),
                                                 cfg["limits"]["max_video_minutes"])
            except Exception as e:
                print(f"[{camp['name']}] ✗ no pude leer {s['url']}: {str(e)[:200]}")
                continue
            for v in videos:
                print(f"[{camp['name']}] nuevo: {v['title']}")
                jobs.append({"campaign": camp["name"], "video": v})
    if len(jobs) > limit:
        # reparte por turnos entre campañas: primero un video de cada una, luego el segundo, etc.
        seen: dict = {}
        for j in jobs:
            j["_turn"] = seen[j["campaign"]] = seen.get(j["campaign"], -1) + 1
        jobs = sorted(jobs, key=lambda j: j["_turn"])[:limit]
        for j in jobs:
            j.pop("_turn")
    return jobs


# ------------------------------------------------------------------ clip
def _shift(segs: list[dict], offset: float) -> list[dict]:
    out = []
    for s in segs:
        out.append({**s, "start": s["start"] - offset, "end": s["end"] - offset,
                    "words": [{**w, "start": w["start"] - offset, "end": w["end"] - offset} for w in s.get("words", [])]})
    return out


def clip_job(job: dict, defaults: dict, camps: list[dict]) -> Path:
    """Procesa un video y deja los clips + manifest.json en output/<campaña>/<video>/."""
    from . import audio, render, transcribe
    camp = _camp(camps, job["campaign"])
    cfg = campaign_config(defaults, camp)
    video, lim, tcfg = job["video"], cfg["limits"], cfg["transcription"]
    outdir = OUTPUT / sources._safe(camp["name"]) / sources._safe(video["id"])
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {"campaign": camp["name"], "video": video, "clips": [], "error": None}
    work = WORK / sources._safe(video["id"])
    print(f"\n▶ [{camp['name']}] {video['title']} ({video['id']})")
    try:
        preview = sources.download_preview(video, work, lim.get("preview_max_height", 360))
        loud = audio.Loudness(preview)
        if loud.duration > lim.get("max_full_transcribe_minutes", 45) * 60:
            windows = loud.peak_windows(lim.get("long_stream_windows", 8))
            print(f"  · {loud.duration / 3600:.1f} h: transcribo los {len(windows)} tramos con más reacción")
            segs = transcribe.transcribe_windows(preview, windows, tcfg["model"], tcfg.get("language"))
        else:
            print(f"  · {loud.duration / 60:.0f} min: transcribiendo todo")
            segs = transcribe.transcribe(preview, tcfg["model"], tcfg.get("language"))
        loud.annotate(segs)
        if not segs:
            manifest["note"] = "sin voz"
            return _write(outdir, manifest)

        context = "\n".join(x for x in [
            f"Canal: {video.get('channel') or camp['name']}", trends.brief_for(camp["name"])] if x)
        print(f"  · {len(segs)} frases ({sum(1 for x in segs if x.get('loud_db'))} con reacción); eligiendo clips…")
        clips = highlights.pick_highlights(segs, video["title"], cfg["highlights"], lim, context)

        for i, clip in enumerate(clips, 1):
            name = f"clip_{i:02d}.mp4"
            print(f"  · clip {i}: {clip['start']:.0f}s-{clip['end']:.0f}s «{clip['title']}» (score {clip['score']})")
            src, c, sg = preview, clip, segs
            try:
                pad = 1.0
                hq = sources.download_section(video, work, clip["start"] - pad, clip["end"] + pad, i,
                                              lim.get("download_max_height", 1080))
                off = max(0.0, clip["start"] - pad)
                src, c, sg = hq, {**clip, "start": clip["start"] - off, "end": clip["end"] - off}, _shift(segs, off)
            except Exception as e:
                print(f"    (no pude bajar el tramo en HD, uso la versión liviana: {str(e)[:120]})")
            render.render_clip(src, outdir / name, c, sg, cfg["render"])
            (outdir / name).with_suffix(".ass").unlink(missing_ok=True)
            manifest["clips"].append({**clip, "file": name, "caption_full": _caption(clip, camp)})
    except Exception as e:
        manifest["error"] = f"{type(e).__name__}: {str(e)[:400]}"
        traceback.print_exc()
    finally:
        for f in work.glob("*"):
            f.unlink(missing_ok=True)
    return _write(outdir, manifest)


def _write(outdir: Path, manifest: dict) -> Path:
    path = outdir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return path


# ------------------------------------------------------------------ publish
def publish_all(folder: Path, defaults: dict, camps: list[dict], no_publish: bool,
                planned: list[dict] | None = None) -> int:
    from . import accounts
    ACCOUNTS.update(accounts.load())
    print(f"Cuentas: {len(ACCOUNTS['tiktok'])} TikTok, {len(ACCOUNTS['facebook'])} Facebook")
    st = state.load()
    summary("| Campaña | Clip | Texto en pantalla | Score | Publicado |\n|---|---|---|---|---|")
    manifests = sorted(folder.rglob("manifest.json"))
    queue, failures = [], 0
    for m in manifests:
        man = json.loads(m.read_text())
        key = f"{man['campaign']}::{man['video']['id']}"
        if man.get("error"):
            failures += 1
            prev = st.get(key, {})
            state.mark(st, key, {"campaign": man["campaign"], "title": man["video"]["title"],
                                 "attempts": prev.get("attempts", 0) + 1, "error": man["error"]})
            print(f"✗ [{man['campaign']}] {man['video']['title']}: {man['error']}")
            continue
        for c in man["clips"]:
            queue.append((m.parent, man, c))
        state.mark(st, key, {"campaign": man["campaign"], "title": man["video"]["title"],
                             "clips": [{k: c[k] for k in ("start", "end", "title", "score")} for c in man["clips"]],
                             **({"note": man["note"]} if man.get("note") else {})})

    # videos planeados cuya máquina se cayó sin dejar resultado (timeout, disco lleno…) = intento fallido
    done = {(json.loads(m.read_text())["campaign"], json.loads(m.read_text())["video"]["id"]) for m in manifests}
    for j in planned or []:
        if (j["campaign"], j["video"]["id"]) not in done:
            failures += 1
            key = f"{j['campaign']}::{j['video']['id']}"
            state.mark(st, key, {"campaign": j["campaign"], "title": j["video"]["title"],
                                 "attempts": st.get(key, {}).get("attempts", 0) + 1, "error": "la máquina no terminó"})
            print(f"✗ [{j['campaign']}] {j['video']['title']}: la máquina no terminó")

    queue.sort(key=lambda q: -q[2].get("score", 0))
    max_posts, posted = defaults["publish"].get("max_posts_per_run", 15), 0
    for folder_, man, c in queue:
        camp = _camp(camps, man["campaign"])
        cfg = campaign_config(defaults, camp)
        do_pub = cfg["publish"].get("enabled") and not no_publish and posted < max_posts
        posts = []
        if do_pub:
            print(f"Publicando [{camp['name']}] «{c['title']}»")
            posts = publish(folder_ / c["file"], c["caption_full"], cfg["publish"], camp)
            posted += 1
            time.sleep(cfg["publish"].get("delay_between_posts_seconds", 0))
        record_submission({
            "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "campaign": camp["name"],
            "source_title": man["video"]["title"], "source_url": man["video"]["url"],
            "channel": man["video"].get("channel"),
            "start": c["start"], "end": c["end"], "title": c["title"], "score": c["score"],
            "on_screen_text": c.get("on_screen_text", ""), "sound_idea": c.get("sound_idea", ""),
            "trend": c.get("trend", ""), "caption": c["caption_full"],
            "file": f"{folder_.parent.name}/{folder_.name}/{c['file']}",
            "posts": posts,
        })
        links = ", ".join(p.get("url") or p.get("status", "") for p in posts) or "(sin publicar)"
        summary(f"| {camp['name']} | {c['title']} | {c.get('on_screen_text', '')} | {c['score']} | {links} |")

    if any(a.pop("_dirty", False) for a in ACCOUNTS["tiktok"]):
        try:
            accounts.save(ACCOUNTS)
        except Exception as e:
            print(f"! No pude guardar los tokens renovados: {e}")
    return failures


# ------------------------------------------------------------------ CLI
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(ROOT / "config.yaml"))
    ap.add_argument("--url", help="procesar solo este video/canal")
    ap.add_argument("--campaign", help="campaña a usar (reglas, hashtags, cuentas)")
    ap.add_argument("--no-publish", action="store_true", help="solo generar los clips")
    ap.add_argument("--plan", metavar="SALIDA.json", help="fase 1: escribir la lista de trabajos")
    ap.add_argument("--clip", metavar="TRABAJO_JSON", help="fase 2: procesar un trabajo")
    ap.add_argument("--publish", metavar="CARPETA", help="fase 3: publicar los clips de una carpeta")
    ap.add_argument("--planned", metavar="PLAN.json", help="lista de trabajos planeados (para detectar fallas)")
    args = ap.parse_args()
    defaults, camps = load_config(Path(args.config))

    if args.plan:
        jobs = plan(defaults, camps, args.url, args.campaign)
        Path(args.plan).write_text(json.dumps(jobs, ensure_ascii=False))
        print(f"{len(jobs)} video(s) para procesar")
        return
    if args.clip:
        man = json.loads(clip_job(json.loads(args.clip), defaults, camps).read_text())
        raise SystemExit(1 if man.get("error") else 0)
    if args.publish:
        planned = json.loads(Path(args.planned).read_text() or "[]") if args.planned else None
        raise SystemExit(1 if publish_all(Path(args.publish), defaults, camps, args.no_publish, planned) else 0)

    jobs = plan(defaults, camps, args.url, args.campaign)
    print(f"{len(jobs)} video(s) para procesar")
    for job in jobs:
        clip_job(job, defaults, camps)
    raise SystemExit(1 if publish_all(OUTPUT, defaults, camps, args.no_publish) else 0)


if __name__ == "__main__":
    main()
