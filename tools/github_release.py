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

"""GitHub-Release anlegen + AppImage hochladen (stdlib-only, eigenstaendig).

Gegenstueck zu forgejo_release.py fuer den oeffentlichen GitHub-Push-Mirror. Ein
Push-Mirror uebertraegt nur Refs, keine Releases/Anhaenge — die muessen von der
eigenen Seite hochgeladen werden. Ablauf (siehe push-mirror-vorbereitung.txt, Punkt 8):
warten, bis der Tag drueben ist -> Release anlegen (idempotent) -> Anhang an
uploads.github.com -> per SHA-256 gegenpruefen.

Konfiguration ausserhalb des Repos (das Repo wird oeffentlich gespiegelt):
  Slug  : $KKM_GITHUB_SLUG  oder  ~/.config/kamera_konfigurationsmanager/github_repo
  Token : $GITHUB_TOKEN     oder  ~/.config/kamera_konfigurationsmanager/github_token
Der Token braucht *Contents: Read and write* auf genau dieses Repo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://api.github.com"
UPLOADS = "https://uploads.github.com"
_CFG_DIR = os.path.expanduser("~/.config/kamera_konfigurationsmanager")


# --------------------------------------------------------------------------- #
# Konfiguration (Slug + Token) — nie fest im Quelltext                         #
# --------------------------------------------------------------------------- #

def _from_env_or_file(env: str, filename: str) -> str:
    v = os.environ.get(env, "").strip()
    if v:
        return v
    try:
        return open(os.path.join(_CFG_DIR, filename), encoding="utf-8").read().strip()
    except OSError:
        return ""


def resolve_slug() -> str:
    slug = _from_env_or_file("KKM_GITHUB_SLUG", "github_repo")
    if not slug:
        raise SystemExit(
            "GitHub-Repo unbekannt. Setze KKM_GITHUB_SLUG (owner/repo) oder lege "
            f"{_CFG_DIR}/github_repo mit dieser einen Zeile an.")
    return slug


def resolve_token() -> str:
    tok = _from_env_or_file("GITHUB_TOKEN", "github_token")
    if not tok:
        raise SystemExit(
            "GitHub-Token fehlt. Setze GITHUB_TOKEN oder lege "
            f"{_CFG_DIR}/github_token an (fine-grained, Contents: Read and write).")
    return tok


# --------------------------------------------------------------------------- #
# Version / Changelog (eigenstaendig gehalten)                                 #
# --------------------------------------------------------------------------- #

def read_version() -> str:
    src = open(os.path.join(ROOT, "kkm", "version.py"), encoding="utf-8").read()
    m = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', src)
    if not m:
        raise SystemExit("Version in kkm/version.py nicht gefunden")
    return m.group(1)


def changelog_notes(version: str) -> str:
    path = os.path.join(ROOT, "CHANGELOG.md")
    if not os.path.exists(path):
        return ""
    out: list[str] = []
    grabbing = False
    head = re.compile(r"^##\s+" + re.escape(version) + r"(\s|$|\s—)")
    for line in open(path, encoding="utf-8").read().splitlines():
        if line.startswith("## "):
            if grabbing:
                break
            grabbing = bool(head.match(line))
            continue
        if grabbing:
            out.append(line)
    return "\n".join(out).strip()


# --------------------------------------------------------------------------- #
# HTTP                                                                         #
# --------------------------------------------------------------------------- #

def _headers(token: str, extra: dict | None = None) -> dict:
    h = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "kkm-release",
    }
    if extra:
        h.update(extra)
    return h


def _request(method: str, url: str, headers: dict, data: bytes | None = None):
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def wait_for_tag(slug: str, tag: str, token: str, timeout: int = 180) -> bool:
    """Pollt, bis der (vom Mirror gepushte) Tag bei GitHub sichtbar ist."""
    url = f"{API}/repos/{slug}/git/ref/tags/{tag}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, _ = _request("GET", url, _headers(token))
        if status == 200:
            return True
        time.sleep(3)
    return False


def get_release_by_tag(slug: str, tag: str, token: str) -> dict | None:
    status, body = _request("GET", f"{API}/repos/{slug}/releases/tags/{tag}",
                            _headers(token))
    return json.loads(body) if status == 200 else None


def create_release(slug: str, version: str, notes: str, draft: bool,
                   token: str) -> dict:
    tag = f"v{version}"
    payload = json.dumps({
        "tag_name": tag,
        "name": tag,
        "body": notes,
        "draft": draft,
        "prerelease": "b" in version,
    }).encode()
    status, body = _request("POST", f"{API}/repos/{slug}/releases",
                            _headers(token), payload)
    if status in (200, 201):
        return json.loads(body)
    raise SystemExit(f"GitHub-Release anlegen fehlgeschlagen (HTTP {status}): "
                     f"{body[:400].decode(errors='replace')}")


def delete_existing_asset(slug: str, release: dict, name: str, token: str) -> None:
    for a in release.get("assets", []) or []:
        if a.get("name") == name:
            _request("DELETE", f"{API}/repos/{slug}/releases/assets/{a['id']}",
                     _headers(token))


def upload_asset(slug: str, release_id: int, path: str, token: str) -> dict:
    name = os.path.basename(path)
    with open(path, "rb") as fh:
        content = fh.read()
    url = f"{UPLOADS}/repos/{slug}/releases/{release_id}/assets?name={name}"
    hdr = _headers(token, {"Content-Type": "application/octet-stream"})
    status, body = _request("POST", url, hdr, content)
    if status in (200, 201):
        return json.loads(body)
    raise SystemExit(f"GitHub-Asset-Upload fehlgeschlagen (HTTP {status}): "
                     f"{body[:400].decode(errors='replace')}")


def verify_asset(browser_url: str, local_path: str) -> bool:
    """Anhang zurueckladen (ohne Anmeldung, oeffentliches Repo) und SHA-256 vergleichen.
    Umgeht die S3-Falle: kein Authorization-Kopf beim Umleiten auf den CDN."""
    want = hashlib.sha256(open(local_path, "rb").read()).hexdigest()
    req = urllib.request.Request(browser_url, headers={"User-Agent": "kkm-release"})
    with urllib.request.urlopen(req) as resp:
        got = hashlib.sha256(resp.read()).hexdigest()
    return want == got


# --------------------------------------------------------------------------- #
# main                                                                         #
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser(
        description="GitHub-Release anlegen + AppImage hochladen (Push-Mirror-Gegenstueck)")
    ap.add_argument("assets", nargs="+",
                    help="Asset-Dateien (AppImage; optional Windows-.exe)")
    ap.add_argument("--version", help="Version (Vorgabe: aus kkm/version.py)")
    ap.add_argument("--draft", action="store_true", help="Als Entwurf anlegen")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts senden")
    ap.add_argument("--wait", type=int, default=180,
                    help="Sekunden auf den Tag bei GitHub warten (Vorgabe 180)")
    args = ap.parse_args()

    version = args.version or read_version()
    tag = f"v{version}"
    assets = [os.path.abspath(a) for a in args.assets]
    for a in assets:
        if not os.path.exists(a):
            raise SystemExit(f"Asset nicht gefunden: {a}")
        if version not in os.path.basename(a):
            print(f"WARNUNG: '{os.path.basename(a)}' enthaelt die Version {version} nicht.",
                  file=sys.stderr)

    slug = resolve_slug()
    notes = changelog_notes(version)
    print(f"GitHub-Release {slug} {tag}" + ("  [Entwurf]" if args.draft else "") + "  Assets:")
    for a in assets:
        print(f"  - {os.path.basename(a)} ({os.path.getsize(a)} Bytes)")
    if not notes:
        print("WARNUNG: kein CHANGELOG-Abschnitt fuer diese Version gefunden.", file=sys.stderr)

    if args.dry_run:
        print("--dry-run: nichts gesendet.")
        return 0

    token = resolve_token()

    print(f"-> Warte auf Tag {tag} bei GitHub (bis {args.wait}s) ...")
    if not wait_for_tag(slug, tag, token, args.wait):
        raise SystemExit(f"Tag {tag} ist nach {args.wait}s nicht bei GitHub angekommen "
                         "(Push-Mirror-Sync fehlgeschlagen?).")

    existing = get_release_by_tag(slug, tag, token)
    if existing:
        print(f"Release {tag} existiert bereits (id {existing['id']}) — wird wiederverwendet.")
        release = existing
    else:
        release = create_release(slug, version, notes, args.draft, token)
        print(f"Release angelegt: id {release['id']}, tag {release['tag_name']}")

    for a in assets:
        delete_existing_asset(slug, release, os.path.basename(a), token)   # idempotent
        up = upload_asset(slug, release["id"], a, token)
        if verify_asset(up.get("browser_download_url", ""), a):
            print(f"Asset hochgeladen + SHA-256 OK: {up.get('name')} {up.get('size')} Bytes")
        else:
            raise SystemExit(f"SHA-256-Gegenprobe FEHLGESCHLAGEN fuer {up.get('name')}.")
    print(f"Fertig: https://github.com/{slug}/releases/tag/{tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
