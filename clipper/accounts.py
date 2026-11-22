"""Cuentas conectadas de TikTok y Facebook.

Los tokens se guardan cifrados en state/accounts.enc con la clave del secret ACCOUNTS_KEY.
Así el sistema puede actualizar los tokens solo (TikTok los rota) sin que tengas que tocar los Secrets.
También acepta cuentas cargadas a mano en los secrets TIKTOK_ACCOUNTS_JSON / FACEBOOK_PAGES_JSON.

Uso (lo llama el workflow "Conectar cuenta" desde el panel):
  python -m clipper.accounts tiktok  <code> <redirect_uri>
  python -m clipper.accounts facebook <token_corto_de_usuario>
"""
import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parent.parent
ENC = ROOT / "state" / "accounts.enc"
PUBLIC = ROOT / "state" / "accounts_public.json"   # solo nombres, sin tokens (lo muestra el panel)
GRAPH = "https://graph.facebook.com/v21.0"


def _fernet() -> Fernet | None:
    secret = os.environ.get("ACCOUNTS_KEY", "")
    if not secret:
        return None
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest()))


def load() -> dict:
    data = {"tiktok": [], "facebook": []}
    f = _fernet()
    if f and ENC.exists() and ENC.read_bytes().strip():
        data = json.loads(f.decrypt(ENC.read_bytes().strip()))
    # cuentas cargadas a mano en los secrets (se suman a las conectadas)
    for key, env in (("tiktok", "TIKTOK_ACCOUNTS_JSON"), ("facebook", "FACEBOOK_PAGES_JSON")):
        raw = os.environ.get(env, "").strip()
        if raw:
            names = {a.get("name") for a in data[key]}
            data[key] += [a for a in json.loads(raw) if a.get("name") not in names]
    return data


def save(data: dict) -> None:
    f = _fernet()
    if not f:
        raise RuntimeError("Falta el secret ACCOUNTS_KEY para guardar cuentas conectadas")
    stored = {k: [a for a in v if a.get("connected")] for k, v in data.items()}
    ENC.write_bytes(f.encrypt(json.dumps(stored).encode()) + b"\n")
    public = {k: [{kk: a.get(kk) for kk in ("name", "username", "page_id", "connected_at")} for a in v]
              for k, v in stored.items()}
    PUBLIC.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n")


def _upsert(items: list, new: dict, key: str) -> None:
    for i, a in enumerate(items):
        if a.get(key) == new.get(key):
            items[i] = {**a, **new}
            return
    items.append(new)


def connect_tiktok(code: str, redirect_uri: str) -> str:
    r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=30,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      data={"client_key": os.environ["TIKTOK_CLIENT_KEY"],
                            "client_secret": os.environ["TIKTOK_CLIENT_SECRET"],
                            "code": code, "grant_type": "authorization_code", "redirect_uri": redirect_uri})
    tok = r.json()
    if "refresh_token" not in tok:
        raise RuntimeError(f"TikTok rechazó el código (¿expiró? vuelve a conectar): {tok}")
    username = display = None
    info = requests.get("https://open.tiktokapis.com/v2/user/info/?fields=open_id,display_name,username",
                        headers={"Authorization": f"Bearer {tok['access_token']}"}, timeout=30).json()
    user = info.get("data", {}).get("user", {})
    username, display = user.get("username"), user.get("display_name")
    name = username or display or tok["open_id"][:8]
    data = load()
    _upsert(data["tiktok"], {"name": name, "username": username, "open_id": tok["open_id"],
                             "refresh_token": tok["refresh_token"], "connected": True,
                             "connected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}, "open_id")
    save(data)
    return f"TikTok conectado: @{name}"


def connect_facebook(short_token: str) -> str:
    r = requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": os.environ["FACEBOOK_APP_ID"],
        "client_secret": os.environ["FACEBOOK_APP_SECRET"], "fb_exchange_token": short_token})
    long_token = r.json().get("access_token")
    if not long_token:
        raise RuntimeError(f"Facebook rechazó el token: {r.json()}")
    pages = requests.get(f"{GRAPH}/me/accounts", params={"access_token": long_token}, timeout=30).json()
    if not pages.get("data"):
        raise RuntimeError("Tu usuario no administra ninguna página. Crea una página primero.")
    data, now = load(), datetime.now(timezone.utc).isoformat(timespec="seconds")
    for p in pages["data"]:
        # el token de página obtenido con un token de usuario de larga duración no vence
        _upsert(data["facebook"], {"name": p["name"], "page_id": p["id"], "access_token": p["access_token"],
                                   "connected": True, "connected_at": now}, "page_id")
    save(data)
    return "Facebook conectado: " + ", ".join(p["name"] for p in pages["data"])


if __name__ == "__main__":
    platform, value = sys.argv[1], sys.argv[2]
    print(connect_tiktok(value, sys.argv[3]) if platform == "tiktok" else connect_facebook(value))
