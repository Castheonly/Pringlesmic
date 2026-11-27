"""Registro de videos ya procesados (se guarda en el repo para que sobreviva entre corridas)."""
import json
from datetime import datetime, timezone
from pathlib import Path

STATE_FILE = Path(__file__).resolve().parent.parent / "state" / "processed.json"


def load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text() or "{}")
    return {}


def save(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def mark(state: dict, video_id: str, info: dict) -> None:
    state[video_id] = {"processed_at": datetime.now(timezone.utc).isoformat(), **info}
    save(state)
