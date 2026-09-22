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

"""Verschluesseltes Sicherungs-Archiv fuer Daten + Passwort-Tresor.

Buendelt die App-Dateien (``groups.json``, ``settings.json``, ``vault.enc``) in
**eine** portable Datei:

    Dateien --tar--> --zlib(deflate)--> --AES-256-GCM--> .kkmbackup

- Nur Python-Standardbibliothek (``tarfile``, ``zlib``, ``hashlib``) plus das schon
  vorhandene ``cryptography`` (AES-256-GCM). Kein externes Programm, kein
  plattformspezifisches Binary -> identisch unter Linux und Windows.
- Der Schluessel wird per PBKDF2-HMAC-SHA256 aus einem **Backup-Passwort**
  abgeleitet; GCM liefert zugleich Integritaetsschutz (falsches Passwort oder
  manipulierte Datei -> Fehler beim Entschluesseln).
- Der ``cryptography``-Import ist wie beim Tresor **deferred**, damit das Modul
  auch ohne gebuendeltes Wheel importierbar bleibt.

Dateiformat (binaer):

    MAGIC (11 B) | salt (16 B) | nonce (12 B) | iterations (4 B, big-endian) | ct

``ct`` = AES-256-GCM(nonce, zlib(tar(dateien)), aad=MAGIC).

(zlib statt LZMA, weil der gebuendelte AppImage-Interpreter ``_lzma`` nicht
enthaelt, ``zlib`` aber immer — die JSON-Daten komprimieren damit gut genug.)
"""

from __future__ import annotations

import io
import zlib
import os
import tarfile
import hashlib

from .groups import open_private
from .vault import MIN_KDF_ITERATIONS, MAX_KDF_ITERATIONS

MAGIC = b"KKMBACKUP1\n"        # Formatkennung + Versions-Tag (zugleich AES-AAD)
KDF_ITERATIONS = 600_000       # wie der Tresor (OWASP-Floor fuer PBKDF2-SHA256)
KEY_LEN = 32                   # AES-256
SALT_LEN = 16
NONCE_LEN = 12
HEADER_LEN = len(MAGIC) + SALT_LEN + NONCE_LEN + 4

#: Nur diese Dateien werden gesichert/wiederhergestellt (Basisnamen, keine Pfade).
BACKUP_FILES = ("groups.json", "settings.json", "vault.enc")


class BackupError(Exception):
    """Falsches Passwort, beschaedigte/fremde Datei oder fehlendes Krypto-Backend."""


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - depends on bundled wheel
        raise BackupError(
            "Das Krypto-Backend 'cryptography' ist nicht verfügbar."
        ) from exc
    return AESGCM


def _derive(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, KEY_LEN
    )


def create_backup(out_path: str, password: str, config_dir: str) -> list[str]:
    """Sichert die vorhandenen App-Dateien aus *config_dir* verschluesselt nach
    *out_path*. Gibt die tatsaechlich enthaltenen Dateinamen zurueck.

    Nicht vorhandene Dateien (z. B. ``vault.enc``, wenn kein Tresor angelegt ist)
    werden uebersprungen.
    """
    if not password:
        raise BackupError("Bitte ein Backup-Passwort angeben.")

    included: list[str] = []
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name in BACKUP_FILES:
            src = os.path.join(config_dir, name)
            if os.path.isfile(src):
                tar.add(src, arcname=name)
                included.append(name)
    if not included:
        raise BackupError("Keine zu sichernden Daten gefunden.")

    plain = zlib.compress(buf.getvalue(), level=9)
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive(password, salt, KDF_ITERATIONS)
    ct = _aesgcm()(key).encrypt(nonce, plain, MAGIC)

    tmp = out_path + ".tmp"
    with open_private(tmp, "wb") as fh:
        fh.write(MAGIC)
        fh.write(salt)
        fh.write(nonce)
        fh.write(KDF_ITERATIONS.to_bytes(4, "big"))
        fh.write(ct)
    os.replace(tmp, out_path)
    return included


def read_backup(in_path: str, password: str) -> dict[str, bytes]:
    """Entschluesselt *in_path* und liefert ``{dateiname: inhalt}``.

    Wirft :class:`BackupError` bei fremdem Format, falschem Passwort oder
    beschaedigter Datei. Es werden nur bekannte Dateinamen (siehe
    :data:`BACKUP_FILES`) zurueckgegeben — Schutz vor manipulierten Archiven.
    """
    try:
        with open(in_path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise BackupError(f"Datei nicht lesbar: {exc}") from exc

    if len(data) < HEADER_LEN or not data.startswith(MAGIC):
        raise BackupError("Keine gültige Backup-Datei (falsches Format).")

    off = len(MAGIC)
    salt = data[off:off + SALT_LEN]; off += SALT_LEN
    nonce = data[off:off + NONCE_LEN]; off += NONCE_LEN
    iterations = int.from_bytes(data[off:off + 4], "big"); off += 4
    ct = data[off:]
    # Die Iterationszahl steht ungeschuetzt im Header: begrenzen, sonst friert eine
    # praeparierte Datei (bis ~4 Mrd. Iterationen) die Oberflaeche ein.
    if not MIN_KDF_ITERATIONS <= iterations <= MAX_KDF_ITERATIONS:
        raise BackupError(
            f"Keine gültige Backup-Datei (unzulässige Iterationszahl {iterations}).")

    key = _derive(password, salt, iterations)
    try:
        plain = _aesgcm()(key).decrypt(nonce, ct, MAGIC)
    except Exception as exc:  # InvalidTag u. a. -> falsches Passwort/manipuliert
        raise BackupError("Falsches Passwort oder beschädigte Backup-Datei.") from exc

    try:
        tar_bytes = zlib.decompress(plain)
    except zlib.error as exc:
        raise BackupError(f"Backup-Inhalt beschädigt: {exc}") from exc

    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        for member in tar.getmembers():
            base = os.path.basename(member.name)   # Pfad-Traversal ausschliessen
            if member.isfile() and base in BACKUP_FILES:
                f = tar.extractfile(member)
                if f is not None:
                    out[base] = f.read()
    if not out:
        raise BackupError("Backup enthält keine bekannten Daten.")
    return out


def restore_backup(in_path: str, password: str, config_dir: str) -> list[str]:
    """Spielt ein Backup in *config_dir* ein (ueberschreibt vorhandene Dateien
    atomar). Gibt die wiederhergestellten Dateinamen zurueck.

    Nur im Archiv enthaltene Dateien werden geschrieben; andere bleiben unberuehrt.
    """
    files = read_backup(in_path, password)      # validiert + entschluesselt zuerst
    os.makedirs(config_dir, exist_ok=True)
    restored: list[str] = []
    for name, content in files.items():
        dst = os.path.join(config_dir, name)
        tmp = dst + ".tmp"
        with open_private(tmp, "wb") as fh:
            fh.write(content)
        os.replace(tmp, dst)
        restored.append(name)
    return restored
