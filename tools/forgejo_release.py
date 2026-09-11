#!/usr/bin/env python3
# Kamera_Konfigurationsmanager - Plugin-basierter Konfigurationsmanager fuer Netzwerkkameras.
# Copyright (C) 2026 Mirik
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Legt ein Forgejo-Release an und laedt das AppImage als Asset hoch.

Stdlib-only (urllib/ssl/json). Zugangsdaten (Nutzer + Token) werden aus
~/.git-credentials gelesen — es wird nichts fest verdrahtet. Der Forgejo-Server
nutzt ein selbstsigniertes Zertifikat, daher wird die TLS-Pruefung bewusst
abgeschaltet (nur dieser eine Host, nur fuer den Release-Upload).

Aufruf (i. d. R. ueber release.sh):
    tools/forgejo_release.py <AppImage> [--version V] [--draft] [--dry-run]

Idempotent: existiert das Release zum Tag schon, wird es wiederverwendet; ein
gleichnamiges Asset wird vor dem Upload ersetzt.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_git(*args) -> str:
    """git im Repo-Wurzelverzeichnis ausfuehren; leerer String bei Fehler."""
    try:
        out = subprocess.run(["git", *args], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 - fehlt git/Remote, faellt der Aufrufer zurueck
        return ""


def _resolve_host() -> str:
    """Forgejo-API-Host (host:port) aus der Umgebung statt fest im Quelltext:
    zuerst ``KKM_FORGEJO_HOST``, sonst eine lokale Datei ausserhalb des Repos.
    Bewusst kein Vorgabewert im Code (das Repo wird oeffentlich gespiegelt)."""
    h = os.environ.get("KKM_FORGEJO_HOST", "").strip()
    if h:
        return h
    cfg = os.path.expanduser(
        "~/.config/kamera_konfigurationsmanager/forgejo_host")
    try:
        h = open(cfg, encoding="utf-8").read().strip()
    except OSError:
        h = ""
    if h:
        return h
    raise SystemExit(
        "Forgejo-Host unbekannt. Setze die Umgebungsvariable KKM_FORGEJO_HOST "
        "(z. B. host:port) oder lege ~/.config/kamera_konfigurationsmanager/"
        "forgejo_host mit dieser einen Zeile an."
    )


def _resolve_owner_repo() -> tuple[str, str]:
    """Owner/Repo aus der origin-URL ableiten (nicht fest im Quelltext).
    Beherrscht ``scheme://[user@]host[:port]/owner/repo(.git)`` und die
    scp-Kurzform ``[user@]host:owner/repo(.git)``; per KKM_FORGEJO_OWNER/REPO
    ueberschreibbar."""
    url = _run_git("config", "--get", "remote.origin.url")
    if "://" in url:
        rest = url.split("://", 1)[1].split("@", 1)[-1]
        path = rest.split("/", 1)[1] if "/" in rest else ""
    else:                                   # scp-Kurzform host:owner/repo.git
        rest = url.split("@", 1)[-1]
        path = rest.split(":", 1)[1] if ":" in rest else ""
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    parts = [p for p in path.split("/") if p]
    owner = os.environ.get("KKM_FORGEJO_OWNER") or (parts[0] if len(parts) >= 2 else "")
    repo = os.environ.get("KKM_FORGEJO_REPO") or (parts[-1] if parts else "")
    return owner, repo


# Forgejo-Instanz (selbstsigniert). Host aus der Umgebung, Owner/Repo aus der Remote-URL.
API_HOST = _resolve_host()
API_BASE = f"https://{API_HOST}/api/v1"
OWNER, REPO = _resolve_owner_repo()

_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE


# --------------------------------------------------------------------------- #
# Version / Changelog                                                         #
# --------------------------------------------------------------------------- #

def read_version() -> str:
    """Liest __version__ aus kkm/version.py."""
    src = open(os.path.join(ROOT, "kkm", "version.py"), encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', src)
    if not m:
        raise SystemExit("Version in kkm/version.py nicht gefunden")
    return m.group(1)


def changelog_notes(version: str) -> str:
    """Zieht den Abschnitt '## <version> — …' aus CHANGELOG.md als Release-Text."""
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        return ""
    lines = open(path, encoding="utf-8").read().splitlines()
    out: list[str] = []
    grabbing = False
    head = re.compile(r"^##\s+" + re.escape(version) + r"(\s|$|\s—)")
    for line in lines:
        if line.startswith("## "):
            if grabbing:            # naechster Abschnitt -> fertig
                break
            grabbing = bool(head.match(line))
            continue
        if grabbing:
            out.append(line)
    return "\n".join(out).strip()


# --------------------------------------------------------------------------- #
# Zugangsdaten                                                                #
# --------------------------------------------------------------------------- #

def read_credentials() -> tuple[str, str]:
    """Liest Nutzer + Token fuer den Forgejo-Host aus ~/.git-credentials."""
    path = os.path.expanduser("~/.git-credentials")
    host_key = API_HOST.replace(":", "%3a")     # git speichert den Port url-kodiert
    for raw in open(path, encoding="utf-8"):
        line = raw.strip()
        if host_key.lower() not in line.lower() and API_HOST.lower() not in line.lower():
            continue
        m = re.match(r"^https?://([^:]+):([^@]+)@", line)
        if m:
            return m.group(1), m.group(2)
    raise SystemExit(
        f"Keine Zugangsdaten fuer {API_HOST} in ~/.git-credentials gefunden"
    )


def _auth_header(user: str, token: str) -> dict[str, str]:
    import base64
    raw = base64.b64encode(f"{user}:{token}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


# --------------------------------------------------------------------------- #
# API-Aufrufe                                                                 #
# --------------------------------------------------------------------------- #

def _request(method: str, url: str, headers: dict, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_SSL) as resp:
            body = resp.read()
            return resp.status, body
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def get_release_by_tag(tag: str, auth: dict) -> dict | None:
    url = f"{API_BASE}/repos/{OWNER}/{REPO}/releases/tags/{tag}"
    status, body = _request("GET", url, auth)
    if status == 200:
        return json.loads(body)
    return None


def create_release(version: str, notes: str, draft: bool, auth: dict) -> dict:
    tag = f"v{version}"
    payload = json.dumps({
        "tag_name": tag,
        "target_commitish": "main",
        "name": tag,
        "body": notes,
        "draft": draft,
        "prerelease": "b" in version,      # bN-Suffix -> Vorabversion
    }).encode()
    hdr = {**auth, "Content-Type": "application/json"}
    url = f"{API_BASE}/repos/{OWNER}/{REPO}/releases"
    status, body = _request("POST", url, hdr, payload)
    if status in (200, 201):
        return json.loads(body)
    raise SystemExit(f"Release anlegen fehlgeschlagen (HTTP {status}): {body[:400].decode(errors='replace')}")


def delete_existing_asset(release: dict, name: str, auth: dict) -> None:
    for a in release.get("assets", []) or []:
        if a.get("name") == name:
            url = f"{API_BASE}/repos/{OWNER}/{REPO}/releases/{release['id']}/assets/{a['id']}"
            _request("DELETE", url, auth)


def sync_push_mirror(auth: dict, attempts: int = 3, delay: float = 6.0) -> None:
    """Stoesst Forgejos Push-Mirror sofort an (sonst laeuft er erst im Intervall).
    Noetig, damit ein frisch per API angelegter Tag zeitnah bei GitHub ankommt.
    Der Endpunkt liefert gelegentlich ein transientes HTTP 500 (z. B. wenn gerade
    ein Sync laeuft) -> ein paar Mal wiederholen, bevor aufgegeben wird."""
    import time
    url = f"{API_BASE}/repos/{OWNER}/{REPO}/push_mirrors-sync"
    last = ""
    for i in range(max(1, attempts)):
        status, body = _request("POST", url, auth)
        if status in (200, 201, 202, 204):
            return
        last = f"HTTP {status}: {body[:200].decode(errors='replace')}"
        if i < attempts - 1:
            time.sleep(delay)
    raise SystemExit(f"Mirror-Sync fehlgeschlagen ({last})")


def upload_asset(release_id: int, path: str, auth: dict) -> dict:
    name = os.path.basename(path)
    boundary = uuid.uuid4().hex
    with open(path, "rb") as fh:
        content = fh.read()
    body = b"".join([
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="attachment"; filename="{name}"\r\n'.encode(),
        b"Content-Type: application/octet-stream\r\n\r\n",
        content,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    hdr = {**auth, "Content-Type": f"multipart/form-data; boundary={boundary}"}
    url = f"{API_BASE}/repos/{OWNER}/{REPO}/releases/{release_id}/assets?name={name}"
    status, resp = _request("POST", url, hdr, body)
    if status in (200, 201):
        return json.loads(resp)
    raise SystemExit(f"Asset-Upload fehlgeschlagen (HTTP {status}): {resp[:400].decode(errors='replace')}")


# --------------------------------------------------------------------------- #
# main                                                                        #
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(description="Forgejo-Release anlegen + AppImage hochladen")
    ap.add_argument("assets", nargs="*",
                    help="Asset-Dateien (AppImage; optional Windows-.exe)")
    ap.add_argument("--version", help="Version (Vorgabe: aus kkm/version.py)")
    ap.add_argument("--draft", action="store_true", help="Als Entwurf anlegen")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts senden")
    ap.add_argument("--sync-mirror", action="store_true",
                    help="Nur den Push-Mirror anstossen (kein Release)")
    args = ap.parse_args()

    # Nur den Push-Mirror anstossen (fuer den GitHub-Release-Schritt in release.sh).
    if args.sync_mirror:
        if args.dry_run:
            print("--dry-run: Mirror-Sync uebersprungen.")
            return 0
        user, token = read_credentials()
        sync_push_mirror(_auth_header(user, token))
        print("Push-Mirror angestossen.")
        return 0

    if not args.assets:
        ap.error("mindestens eine Asset-Datei ist erforderlich (ausser bei --sync-mirror)")

    version = args.version or read_version()
    tag = f"v{version}"
    assets = [os.path.abspath(a) for a in args.assets]
    for a in assets:
        if not os.path.exists(a):
            raise SystemExit(f"Asset nicht gefunden: {a}")
        # Plausibilitaet: passt die Datei zur Version?
        if version not in os.path.basename(a):
            print(f"WARNUNG: '{os.path.basename(a)}' enthaelt die Version {version} nicht.",
                  file=sys.stderr)

    notes = changelog_notes(version)
    print(f"Release {tag}" + ("  [Entwurf]" if args.draft else "") + "  Assets:")
    for a in assets:
        print(f"  - {os.path.basename(a)} ({os.path.getsize(a)} Bytes)")
    if notes:
        print("Release-Notes aus CHANGELOG.md uebernommen "
              f"({len(notes.splitlines())} Zeilen).")
    else:
        print("WARNUNG: kein CHANGELOG-Abschnitt fuer diese Version gefunden.", file=sys.stderr)

    if args.dry_run:
        print("--dry-run: nichts gesendet.")
        return 0

    user, token = read_credentials()
    auth = _auth_header(user, token)

    existing = get_release_by_tag(tag, auth)
    if existing:
        print(f"Release {tag} existiert bereits (id {existing['id']}) — wird wiederverwendet.")
        release = existing
    else:
        release = create_release(version, notes, args.draft, auth)
        print(f"Release angelegt: id {release['id']}, tag {release['tag_name']}")

    for a in assets:
        delete_existing_asset(release, os.path.basename(a), auth)   # idempotent
        up = upload_asset(release["id"], a, auth)
        print(f"Asset hochgeladen: {up.get('name')} {up.get('size')} Bytes")
    print(f"Fertig: {API_BASE.replace('/api/v1','')}/{OWNER}/{REPO}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
