"""Fusiona los cambios de state/ de esta corrida con los que otra corrida subió mientras tanto.

Uso: python -m clipper.state_merge BASE_DIR OURS_DIR TARGET_DIR
  BASE  = state/ como estaba al empezar la corrida
  OURS  = state/ con los cambios de esta corrida
  TARGET= state/ recién bajado de GitHub (cambios de otras corridas); se escribe el resultado aquí
"""
import json
import shutil
import sys
from pathlib import Path

# listas de objetos que se fusionan por una clave
KEYED = {"campaign_inbox.json": "url", "discovered.json": "url"}


def _load(p: Path):
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def merge_file(name: str, base, ours, theirs):
    if ours == base:
        return theirs
    if theirs is None or theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict):
        out = dict(theirs)
        for k, v in ours.items():
            if not isinstance(base, dict) or base.get(k) != v:
                out[k] = v
        return out
    if isinstance(ours, list) and isinstance(theirs, list):
        key = KEYED.get(name)
        if key:
            out = {x.get(key): x for x in theirs}
            base_items = {x.get(key): x for x in (base or [])}
            for x in ours:
                if base_items.get(x.get(key)) != x:
                    out[x.get(key)] = x
            return list(out.values())
        new = [x for x in ours if x not in (base or []) and x not in theirs]
        return theirs + new
    return ours


def main(base_dir: str, ours_dir: str, target_dir: str) -> None:
    base_d, ours_d, target_d = Path(base_dir), Path(ours_dir), Path(target_dir)
    for f in ours_d.iterdir():
        if not f.is_file():
            continue
        t = target_d / f.name
        if f.suffix != ".json":
            # binarios (accounts.enc): gana el nuestro si cambió en esta corrida
            b = base_d / f.name
            if not b.exists() or b.read_bytes() != f.read_bytes():
                shutil.copy(f, t)
            continue
        merged = merge_file(f.name, _load(base_d / f.name), _load(f), _load(t))
        t.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
