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

"""Trust-on-First-Use (TOFU) fuer Kamera-Zertifikate.

Kameras nutzen selbstsignierte Zertifikate, eine CA-Pruefung scheidet daher aus.
Stattdessen wird beim ersten HTTPS-Kontakt der SHA-256-Fingerprint des Zertifikats
pro Kamera (``camera_key``, also MAC/Seriennummer — nicht die IP) gespeichert und
bei jedem weiteren Verbindungsaufbau verglichen. Weicht er ab, wird die Verbindung
abgebrochen, **bevor** eine Anfrage und damit Zugangsdaten gesendet werden
(:class:`CertMismatch`); die GUI fragt dann nach.

Zusaetzlich verhindert die Pruefung den Downgrade-Trick: Ist fuer eine Kamera ein
Zertifikat bekannt und scheitert der HTTPS-Verbindungsaufbau, wird im Modus
``auto`` nicht auf HTTP zurueckgefallen (:class:`HttpFallbackRefused`).

Die HTTP-Clients der Plugins sind stdlib-only und kennen nur ``ip:port``. Die
Zuordnung zur Kamera laeuft ueber einen thread-lokalen Kontext: die GUI klammert
jeden Kamera-Zugriff mit :func:`bound`; der ueber
``kkm.plugins.set_connect_hook(check_connection)`` eingehaengte Hook liest ihn beim
Verbindungsaufbau. Ohne Kontext (Discovery, Online-Pruefung) wird nichts geprueft.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager

from .groups import config_dir, open_private
from .i18n import t

FILENAME = "known_certs.json"


def fingerprint(der: bytes) -> str:
    """SHA-256 des DER-Zertifikats als Hex-String."""
    return hashlib.sha256(der).hexdigest()


def short_fp(fp: str | None) -> str:
    """Kurzform fuer die Anzeige: ``ab:cd:ef:…:12:34``."""
    if not fp:
        return "—"
    pairs = [fp[i:i + 2] for i in range(0, len(fp), 2)]
    return ":".join(pairs[:4]) + ":…:" + ":".join(pairs[-2:])


class CertMismatch(Exception):
    """Zertifikat weicht vom gespeicherten ab — Verbindung vor dem Senden abgebrochen.

    Bewusst KEIN OSError: die Upload-Routinen der Clients werten Verbindungsfehler als
    "Geraet startet neu" (Erfolg); diese Ablehnung darf dort nicht verschluckt werden."""

    cert_mismatch = True

    def __init__(self, camera_key: str, expected: str, actual: str):
        self.camera_key = camera_key
        self.expected = expected
        self.actual = actual
        super().__init__(t(
            "Zertifikat der Kamera hat sich geändert (bekannt {old}, jetzt {new}) — "
            "Verbindung abgebrochen, keine Zugangsdaten gesendet. Ist die Änderung "
            "erwartet: Rechtsklick → „Zertifikat vergessen“.",
            old=short_fp(expected), new=short_fp(actual)))


class HttpFallbackRefused(ConnectionError):
    """HTTPS nicht erreichbar, fuer die Kamera ist aber ein Zertifikat bekannt -> kein
    Rueckfall auf unverschluesseltes HTTP. Als OSError zaehlt das fuer die Clients wie
    "ueber dieses Schema nicht erreichbar"."""


class CertStore:
    """``camera_key -> {"sha256": fp, "seen": "JJJJ-MM-TT"}`` in ``known_certs.json``.

    Liest bei jedem Zugriff frisch von der Platte (kleine Datei) — so bleibt der Stand
    auch nach einem Wiederherstellen der Sicherung ohne Neustart konsistent. Schreiben
    ist per Lock serialisiert (Zugriffe kommen aus parallelen Worker-Threads)."""

    def __init__(self, path: str | None = None):
        self._path = path
        self._lock = threading.RLock()

    @property
    def path(self) -> str:
        if self._path is None:
            self._path = os.path.join(config_dir(), FILENAME)
        return self._path

    def _load(self) -> dict:
        try:
            with open(self.path, encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        with open_private(tmp) as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, self.path)

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._load().get(key)
        return entry.get("sha256") if isinstance(entry, dict) else None

    def remember(self, key: str, fp: str) -> None:
        with self._lock:
            data = self._load()
            data[key] = {"sha256": fp, "seen": time.strftime("%Y-%m-%d")}
            self._save(data)

    def forget(self, keys) -> int:
        with self._lock:
            data = self._load()
            n = sum(1 for k in keys if data.pop(k, None) is not None)
            if n:
                self._save(data)
        return n

    def rekey(self, old_key: str, new_key: str) -> None:
        with self._lock:
            data = self._load()
            if old_key in data:
                data[new_key] = data.pop(old_key)
                self._save(data)

    def keys(self) -> set[str]:
        with self._lock:
            return set(self._load())

    def clear(self) -> int:
        with self._lock:
            n = len(self._load())
            if n:
                self._save({})
        return n


STORE = CertStore()
_enabled = True
_local = threading.local()


def set_enabled(enabled: bool) -> None:
    """TOFU-Pruefung global an/aus (Einstellung ``cert_pinning``)."""
    global _enabled
    _enabled = bool(enabled)


def is_enabled() -> bool:
    return _enabled


class _Context:
    __slots__ = ("key", "scheme", "relearn", "https_failed")

    def __init__(self, key, scheme):
        self.key = key
        self.scheme = scheme
        self.relearn = False        # nach Werksreset/Firmware: jedes Zertifikat uebernehmen
        self.https_failed = False   # HTTPS-Verbindungsaufbau zuletzt gescheitert


@contextmanager
def bound(camera_key: str, scheme: str = "auto"):
    """Ordnet alle Verbindungen des aktuellen Threads im ``with``-Block der Kamera
    *camera_key* zu. *scheme* ist das in den Zugangsdaten gewaehlte Schema — der
    HTTP-Rueckfall wird nur im Modus ``auto`` unterbunden (explizit ``http`` bleibt)."""
    prev = getattr(_local, "ctx", None)
    _local.ctx = _Context(camera_key, scheme or "auto")
    try:
        yield
    finally:
        _local.ctx = prev


def expect_new_certificate() -> None:
    """Im laufenden Kontext aufrufen, nachdem das Programm selbst einen
    Zertifikatswechsel ausgeloest hat (Werksreset, Firmware-Update): das gespeicherte
    Zertifikat wird verworfen und fuer den Rest des Kontexts jedes gesehene
    uebernommen (erst das alte, nach dem Neustart das neue — das zuletzt gesehene
    bleibt gespeichert)."""
    ctx = getattr(_local, "ctx", None)
    if ctx is None or not ctx.key:
        return
    ctx.relearn = True
    STORE.forget([ctx.key])


def check_connection(scheme: str, host: str, port, der: bytes | None) -> None:
    """Connect-Hook der HTTP-Clients (siehe ``kkm.plugins.set_connect_hook``).

    - ``https`` mit *der*: Verbindung steht, Zertifikat pruefen/lernen.
    - ``https`` ohne *der*: Verbindungsaufbau gescheitert (fuer den Downgrade-Schutz).
    - ``http``: wird gleich aufgebaut — ggf. als Downgrade ablehnen.
    """
    ctx = getattr(_local, "ctx", None)
    if ctx is None or not ctx.key or not _enabled:
        return
    if scheme == "https":
        if der is None:
            ctx.https_failed = True
            return
        ctx.https_failed = False
        fp = fingerprint(der)
        known = STORE.get(ctx.key)
        if known == fp:
            return
        if known is None or ctx.relearn:
            STORE.remember(ctx.key, fp)
            return
        raise CertMismatch(ctx.key, known, fp)
    if (scheme == "http" and ctx.scheme == "auto" and ctx.https_failed
            and STORE.get(ctx.key)):
        raise HttpFallbackRefused(t(
            "HTTPS nicht erreichbar, für diese Kamera ist aber ein Zertifikat bekannt — "
            "kein Rückfall auf unverschlüsseltes HTTP. Verbindung „http“ wählen oder "
            "das Zertifikat vergessen, falls HTTPS bewusst abgeschaltet wurde."))
