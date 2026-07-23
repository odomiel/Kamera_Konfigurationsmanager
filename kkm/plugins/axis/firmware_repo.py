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

"""Axis firmware repository — look up and download AXIS OS releases.

Axis publishes no firmware API; the only machine-readable source is the public
software tree, an Apache directory index:

``https://ftp.axis.com/pub_soft/MPQT/<model-dir>/``
    ``12_11_72/``   one directory per release (version with ``_`` instead of ``.``)
    ``latest/``     the newest release of the active track, containing
        ``ver.txt``     the version in plain text, e.g. ``12.11.72``
        ``<model>.bin`` the firmware itself (older devices: ``AXIS_<model>.bin``,
                        so the name must be read from the index, never guessed)

**Host matters.** Over ``www.axis.com/ftp/...`` the ``.bin`` answers 302 to the
My-Axis login; over ``ftp.axis.com`` the same file is served anonymously via HTTPS
with Range support — hence the base URL below. Only the directory listing and
``ver.txt`` are parsed, so a layout change on Axis' side degrades to a clear error
and the user can still assign a ``.bin`` by hand.

Stdlib-only (like :mod:`kkm.plugins.axis.vapix`) — no new dependency.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from kkm.core import t
from kkm.core.camera import version_tuple
from kkm.core.groups import config_dir

BASE_URL = "https://ftp.axis.com/pub_soft/MPQT/"
INDEX_FILENAME = "axis_firmware_index.json"   # Modellordner-Liste (Cache)
INDEX_TTL = 24 * 3600                         # Cache-Alter, ab dem neu geladen wird
CACHE_DIRNAME = "firmware_cache"              # heruntergeladene .bin-Dateien
TIMEOUT = 25
CHUNK = 256 * 1024

# Verzeichniseintraege eines Apache-Index: <a href="M3085-V/"> bzw. <a href="x.bin">
_DIR_RE = re.compile(rb'href="([^"?/]+)/"')
_BIN_RE = re.compile(rb'href="([^"?/]+\.bin)"')


class RepoError(Exception):
    """Firmware-Verzeichnis nicht erreichbar / Modell unbekannt / Layout geaendert."""


@dataclass
class Release:
    """Eine konkrete Firmware-Version eines Modells."""
    model: str          # Ordnername im Repo, z. B. "M3085-V"
    version: str        # "12.11.72"
    url: str            # vollstaendige Download-URL der .bin
    filename: str       # "M3085-V.bin"
    size: int = 0       # Bytes (aus Content-Length; 0 = unbekannt)
    notes_url: str = ""  # relnote.txt


# --------------------------------------------------------------------- HTTP
# Uebliche CA-Speicher der Distributionen — Rueckfall fuer Umgebungen, in denen das
# ssl-Modul keinen kennt.
_CA_PATHS = (
    "/etc/ssl/certs/ca-certificates.crt",     # Debian/Ubuntu
    "/etc/pki/tls/certs/ca-bundle.crt",       # RHEL/Fedora
    "/etc/ssl/ca-bundle.pem",                 # SUSE
    "/etc/ssl/cert.pem",                      # Alpine/BSD/macOS
)


@functools.cache
def _ssl_context() -> ssl.SSLContext:
    """Geprueftes TLS. Anders als bei den Kameras (selbstsignierte Zertifikate,
    ungeprueft) wird hier eine **fremde** Datei geladen, die anschliessend auf die
    Kamera geschrieben wird — die Zertifikatspruefung darf also nicht entfallen.

    Das im AppImage selbst gebaute OpenSSL kennt keinen CA-Speicher; findet das
    ssl-Modul keinen, wird der des Systems nachgereicht (das AppRun setzt dafuer
    ausserdem SSL_CERT_FILE).
    """
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca"):
        return ctx
    for path in _CA_PATHS:
        if os.path.isfile(path):
            try:
                ctx.load_verify_locations(cafile=path)
                return ctx
            except (OSError, ssl.SSLError):
                continue
    raise RepoError(t("Kein Zertifikatsspeicher gefunden — HTTPS-Verbindung zum "
                    "Firmware-Verzeichnis nicht pruefbar. SSL_CERT_FILE setzen "
                    "oder die Firmware von Hand zuweisen."))


def _urlopen(req, timeout: int = TIMEOUT):
    return urllib.request.urlopen(req, timeout=timeout, context=_ssl_context())


def _get(url: str, timeout: int = TIMEOUT) -> bytes:
    try:
        with _urlopen(url, timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise RepoError(f"{url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RepoError(t("{url} nicht erreichbar: {err}", url=url, err=exc)) from exc


def _base(base_url: str | None = None) -> str:
    url = (base_url or BASE_URL).strip() or BASE_URL
    return url if url.endswith("/") else url + "/"


# ------------------------------------------------------------- Versionen
def is_newer(candidate: str, current: str) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    return version_tuple(candidate) > version_tuple(current)


def _major(version: str) -> int:
    return version_tuple(version)[0]


def sort_versions(versions: list[str]) -> list[str]:
    """Neueste zuerst."""
    return sorted(versions, key=version_tuple, reverse=True)


def pick_recommended(versions: list[str], current: str, prefer_track: bool = True) -> str | None:
    """Vorschlag fuer das Update.

    Mit *prefer_track* (Voreinstellung) bleibt der Vorschlag in der **Hauptversion
    der Kamera** — eine Kamera auf 10.12.x bekommt also 10.12.338 vorgeschlagen und
    springt nicht ungefragt vom LTS- auf den Active-Track (12.x). Gibt es im
    aktuellen Track nichts Neueres (oder ist die Firmware der Kamera unbekannt),
    faellt der Vorschlag auf die neueste Version ueberhaupt zurueck.
    """
    ordered = sort_versions(versions)
    if not ordered:
        return None
    if prefer_track and current:
        same = [v for v in ordered if _major(v) == _major(current)]
        if same and is_newer(same[0], current):
            return same[0]
    newest = ordered[0]
    return newest if is_newer(newest, current) else None


# ------------------------------------------------------- Modellordner-Index
def _index_path() -> str:
    return os.path.join(config_dir(), INDEX_FILENAME)


def _load_index_cache(max_age: int = INDEX_TTL) -> list[str] | None:
    path = _index_path()
    try:
        if time.time() - os.path.getmtime(path) > max_age:
            return None
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        models = data.get("models")
        return models if isinstance(models, list) and models else None
    except (OSError, ValueError):
        return None


def _save_index_cache(models: list[str]) -> None:
    try:
        with open(_index_path(), "w", encoding="utf-8") as fh:
            json.dump({"models": models, "fetched": int(time.time())}, fh)
    except OSError:
        pass  # Cache ist nur Optimierung — Fehler duerfen die Suche nicht stoppen


def model_index(base_url: str | None = None, refresh: bool = False) -> list[str]:
    """Alle Modellordner des Repos (rund 680). Wird tagesaktuell zwischengespeichert."""
    if not refresh:
        cached = _load_index_cache()
        if cached:
            return cached
    raw = _get(_base(base_url))
    models = [m.decode("utf-8", "replace") for m in _DIR_RE.findall(raw)]
    if not models:
        raise RepoError(t("Firmware-Verzeichnis lieferte keine Modelle "
                        "(Aufbau der Seite geaendert?)."))
    _save_index_cache(models)
    return models


def _normalize(name: str) -> str:
    """Modellname -> Vergleichsform des Ordnernamens („AXIS M3085-V" -> „m3085-v")."""
    name = (name or "").strip()
    name = re.sub(r"^axis\s+", "", name, flags=re.IGNORECASE)
    # Modellnamen enthalten oft Zusaetze („Network Camera"), Ordner nie.
    name = re.sub(r"\s+(network|fixed|dome|box|bullet)\b.*$", "", name, flags=re.IGNORECASE)
    return re.sub(r"[\s_]+", "_", name).strip("_").lower()


def resolve_model(model: str, base_url: str | None = None) -> str:
    """Modellnamen der Kamera auf einen Ordner im Repo abbilden.

    Die Kamera meldet „AXIS M3085-V", der Ordner heisst „M3085-V" — das deckt die
    Masse ab. Fuer Sonderfaelle (z. B. „Companion_Dome_V") bleibt ein eindeutiger
    Praefix-Treffer als Rueckfall; ist nichts eindeutig, wird ``RepoError``
    geworfen und der Nutzer weist die Datei wie bisher von Hand zu.
    """
    wanted = _normalize(model)
    if not wanted:
        raise RepoError(t("Kein Modellname bekannt."))
    models = model_index(base_url)
    by_norm = {_normalize(m): m for m in models}
    if wanted in by_norm:
        return by_norm[wanted]
    hits = [orig for norm, orig in by_norm.items()
            if norm.startswith(wanted) or wanted.startswith(norm)]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        raise RepoError(t("Modell „{model}“ ist im Firmware-Verzeichnis nicht eindeutig ({hits} …).",
                        model=model, hits=', '.join(sorted(hits)[:4])))
    raise RepoError(t("Modell „{model}“ im Firmware-Verzeichnis nicht gefunden.", model=model))


# ------------------------------------------------------- Versionen je Modell
def versions(model_dir: str, base_url: str | None = None) -> list[str]:
    """Alle im Repo liegenden Versionen eines Modells, neueste zuerst.

    Aeltere Produkte haben nur ``latest/`` (keine Versionsordner) — dann liefert
    ``latest/ver.txt`` die einzige Version.
    """
    raw = _get(f"{_base(base_url)}{model_dir}/")
    found = [d.decode("utf-8", "replace") for d in _DIR_RE.findall(raw)]
    vers = [d.replace("_", ".") for d in found if d[:1].isdigit()]
    if not vers:
        latest = latest_version(model_dir, base_url)
        return [latest] if latest else []
    return sort_versions(vers)


def latest_version(model_dir: str, base_url: str | None = None) -> str:
    """Version aus ``latest/ver.txt`` (die neueste des Active-Tracks)."""
    try:
        return _get(f"{_base(base_url)}{model_dir}/latest/ver.txt").decode(
            "utf-8", "replace").strip()
    except RepoError:
        return ""


def release(model_dir: str, version: str | None = None,
            base_url: str | None = None) -> Release:
    """Download-Daten einer Version. ``version=None`` -> Inhalt von ``latest/``.

    Der Dateiname wird aus dem Verzeichnis-Index gelesen (mal ``M3085-V.bin``, mal
    ``AXIS_P3214.bin``), die Groesse per Range-Anfrage aus dem Content-Range-Header
    (HEAD beantwortet der Server nicht).
    """
    sub = "latest" if version is None else version.replace(".", "_")
    dir_url = f"{_base(base_url)}{model_dir}/{sub}/"
    raw = _get(dir_url)
    bins = [b.decode("utf-8", "replace") for b in _BIN_RE.findall(raw)]
    if not bins:
        raise RepoError(f"Keine .bin-Datei unter {dir_url}.")
    filename = bins[0]
    ver = version
    if ver is None:
        ver = _get(dir_url + "ver.txt").decode("utf-8", "replace").strip()
    url = dir_url + filename
    return Release(model=model_dir, version=ver, url=url, filename=filename,
                   size=_remote_size(url), notes_url=dir_url + "relnote.txt")


def _remote_size(url: str) -> int:
    """Dateigroesse ohne Download: 1 Byte per Range holen und Content-Range lesen."""
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    try:
        with _urlopen(req) as resp:
            rng = resp.headers.get("Content-Range") or ""
            if "/" in rng:
                total = rng.rsplit("/", 1)[1].strip()
                if total.isdigit():
                    return int(total)
            length = resp.headers.get("Content-Length")
            return int(length) if (length or "").isdigit() else 0
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return 0


# ------------------------------------------------------------------ Download
def cache_dir() -> str:
    path = os.path.join(config_dir(), CACHE_DIRNAME)
    os.makedirs(path, exist_ok=True)
    return path


def cached_path(rel: Release) -> str:
    """Zielpfad im Cache: ``<cache>/<Modell>/<Version>/<Originalname>``.

    Modell und Version stecken im *Pfad*, nicht im Dateinamen — so bleibt der
    Dateiname des Herstellers erhalten (er geht beim Upload als Multipart-Dateiname
    an die Kamera), und zwei Versionen ueberschreiben sich trotzdem nicht.
    """
    sub = os.path.join(cache_dir(), rel.model, rel.version.replace(".", "_"))
    os.makedirs(sub, exist_ok=True)
    return os.path.join(sub, rel.filename)


def cache_size() -> int:
    total = 0
    for root, _dirs, files in os.walk(cache_dir()):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def clear_cache() -> None:
    shutil.rmtree(cache_dir(), ignore_errors=True)


def download(rel: Release, progress=None, cancelled=None) -> str:
    """Laedt die Firmware in den Cache und liefert den Pfad.

    Liegt die Datei vollstaendig im Cache, wird sie ohne Netzzugriff verwendet. Ein
    abgebrochener Download wird als ``.part`` fortgesetzt (Range). ``progress(done,
    total)`` wird waehrend des Ladens aufgerufen (laeuft im Worker-Thread!),
    ``cancelled()`` bricht ab, sobald es True liefert.
    """
    dest = cached_path(rel)
    if os.path.exists(dest) and (not rel.size or os.path.getsize(dest) == rel.size):
        if progress:
            progress(os.path.getsize(dest), os.path.getsize(dest))
        return dest

    part = dest + ".part"
    done = os.path.getsize(part) if os.path.exists(part) else 0
    if rel.size and done >= rel.size:      # unvollstaendiger Rest passt nicht -> neu
        done = 0
    headers = {"Range": f"bytes={done}-"} if done else {}
    req = urllib.request.Request(rel.url, headers=headers)
    try:
        with _urlopen(req) as resp:
            if done and resp.status != 206:   # Server ignoriert Range -> von vorn
                done = 0
            total = rel.size or done + int(resp.headers.get("Content-Length") or 0)
            mode = "ab" if done else "wb"
            with open(part, mode) as fh:
                while True:
                    if cancelled and cancelled():
                        raise RepoError("Download abgebrochen.")
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    except urllib.error.HTTPError as exc:
        raise RepoError(t("Download fehlgeschlagen: HTTP {code}", code=exc.code)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RepoError(t("Download fehlgeschlagen: {err}", err=exc)) from exc

    if rel.size and os.path.getsize(part) != rel.size:
        raise RepoError("Download unvollstaendig (Groesse weicht ab).")
    os.replace(part, dest)
    return dest
