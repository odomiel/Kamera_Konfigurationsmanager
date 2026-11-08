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

"""Encrypted password vault.

Camera passwords are stored in a file encrypted with a key derived from a single
**master password**. Design (per the project decision):

    master password --PBKDF2-HMAC-SHA256--> 256-bit key --AES-256-GCM--> ciphertext

- KDF is stdlib (``hashlib.pbkdf2_hmac``) so no extra dependency for key
  derivation. (Argon2 is a planned upgrade; the on-disk ``kdf`` field records the
  scheme so the format can evolve without breaking old vaults.)
- AES-256-GCM provides confidentiality *and* integrity (tamper detection) and
  comes from the ``cryptography`` package — the one runtime dependency to vendor
  as a wheel for the AppImage/Windows build. The import is deferred so the rest of
  the app runs (and the GUI loads) even before that wheel is bundled.

This honours "portable, no OS keyring, no database": everything lives in one file
next to ``groups.json``.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import json
import os
import platform

from .groups import config_dir, open_private

PBKDF2_ITERATIONS = 600_000   # OWASP-recommended floor for PBKDF2-HMAC-SHA256
KDF_NAME = "pbkdf2-hmac-sha256"
# Plausibilitaetsgrenzen fuer eine aus einer Datei gelesene Iterationszahl: nach
# unten gegen absichtlich geschwaechte Dateien, nach oben gegen manipulierte Werte,
# die die Schluesselableitung minuten- bis stundenlang blockieren wuerden.
MIN_KDF_ITERATIONS = 100_000
MAX_KDF_ITERATIONS = 10_000_000
KEY_LEN = 32                  # AES-256
SALT_LEN = 16
NONCE_LEN = 12

# Auto-Entsperrung (Bequemlichkeit, KEIN echter Schutz): das Master-Passwort wird
# in einer Zusatzdatei abgelegt, verschluesselt mit einem aus stabilen Geraete-/
# Benutzermerkmalen abgeleiteten Schluessel. Das bindet die Datei an dieses Konto
# auf diesem Rechner (Kopieren auf einen anderen Rechner schlaegt fehl), ist aber
# gegen jemanden, der als dieser Benutzer Code ausfuehren kann, nicht sicher.
AUTO_FILENAME = "vault.auto"
AUTO_ITERATIONS = 200_000
# Zusatz-Geheimnis der Auto-Entsperrung: ein zufaelliger Per-Install-Wert, der NICHT
# mit vault.auto/vault.enc mitwandert (nicht in der Backup-Allowlist). Er geht in die
# Schluesselableitung ein, sodass das blosse Kennen von Rechnername+Benutzer (oder ein
# wiederhergestelltes Backup) nicht mehr ausreicht. Unter Windows wird er zusaetzlich per
# DPAPI an das Konto gebunden — dann ist eine auf einen anderen Rechner kopierte
# portable Installation (Stick) dort nutzlos. Fehlt die Datei, verhaelt sich die
# Ableitung wie zuvor (Abwaertskompatibilitaet: bestehende Tokens brechen nicht).
AUTO_SECRET_FILENAME = "vault.seed"


def _getuser() -> str:
    try:
        return getpass.getuser()
    except Exception:  # pragma: no cover - je nach Umgebung
        return "user"


# --------------------------------------------------------------------------- #
# Windows DPAPI (optional, an das Benutzerkonto gebunden) — stdlib-only ueber ctypes  #
# --------------------------------------------------------------------------- #

def _dpapi(protect: bool, data: bytes) -> bytes:
    """CryptProtectData/CryptUnprotectData (Windows). Bindet *data* an das aktuelle
    Konto+Rechner. Wirft bei Fehler/Nicht-Windows — der Aufrufer faengt das ab."""
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _blob(b: bytes) -> _BLOB:
        buf = ctypes.create_string_buffer(b, len(b))
        return _BLOB(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.windll.crypt32            # nur auf Windows vorhanden
    kernel32 = ctypes.windll.kernel32
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    out = _BLOB()
    CRYPTPROTECT_UI_FORBIDDEN = 0x1
    ok = fn(ctypes.byref(_blob(data)), None, None, None, None,
            CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out))
    if not ok:
        raise OSError("DPAPI-Aufruf fehlgeschlagen")
    try:
        return ctypes.string_at(out.pbData, out.cbData)
    finally:
        kernel32.LocalFree(out.pbData)


def _autounlock_secret(directory: str, create: bool) -> bytes:
    """Liefert das Per-Install-Geheimnis fuer die Auto-Entsperrung (siehe
    :data:`AUTO_SECRET_FILENAME`). *create*: beim Einrichten der Auto-Entsperrung ein
    neues erzeugen; beim Start nur lesen. Fehlt es (und *create* ist falsch), wird ``b""``
    zurueckgegeben — die Ableitung bleibt dann abwaertskompatibel."""
    path = os.path.join(directory, AUTO_SECRET_FILENAME)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                blob = json.load(fh)
            roh = base64.b64decode(blob["data"])
            return _dpapi(False, roh) if blob.get("dpapi") else roh
        except Exception:  # noqa: BLE001 - fremder Rechner (DPAPI) / beschaedigt -> gesperrt
            return b""
    if not create:
        return b""
    secret = os.urandom(32)
    gespeichert, dpapi = secret, False
    if os.name == "nt":
        try:
            gespeichert, dpapi = _dpapi(True, secret), True
        except Exception:  # noqa: BLE001 - DPAPI nicht verfuegbar -> roher Zufallswert
            gespeichert, dpapi = secret, False
    tmp = path + ".tmp"
    with open_private(tmp) as fh:
        json.dump({"dpapi": dpapi, "data": base64.b64encode(gespeichert).decode()}, fh)
    os.replace(tmp, path)
    return secret


def check_iterations(value) -> int:
    """Validiert eine aus einer Datei gelesene PBKDF2-Iterationszahl.
    Wirft ValueError, wenn sie kein int oder ausserhalb der Grenzen ist."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"ungültige Iterationszahl: {value!r}")
    if not MIN_KDF_ITERATIONS <= value <= MAX_KDF_ITERATIONS:
        raise ValueError(f"Iterationszahl außerhalb des zulässigen Bereichs: {value}")
    return value


def _machine_key(salt: bytes, iterations: int = AUTO_ITERATIONS,
                 secret: bytes = b"") -> bytes:
    ident = "\x1f".join([
        platform.node(), _getuser(), platform.system(),
        "kkm-vault-autounlock-v1",
    ])
    material = ident.encode("utf-8")
    # Per-Install-Geheimnis anhaengen, falls vorhanden; ohne (b"") bleibt die Ableitung
    # identisch zur bisherigen (Abwaertskompatibilitaet bestehender Tokens).
    if secret:
        material += b"\x1f" + secret
    return hashlib.pbkdf2_hmac("sha256", material, salt, iterations, KEY_LEN)


class VaultLocked(Exception):
    """Raised when an operation needs an unlocked vault but it is locked."""


class VaultError(Exception):
    """Wrong master password, corrupt file, or missing crypto backend."""


def _aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:  # pragma: no cover - depends on bundled wheel
        raise VaultError(
            "Das Krypto-Backend 'cryptography' ist nicht verfügbar. "
            "Für den Passwort-Tresor muss das cryptography-Wheel gebündelt werden."
        ) from exc
    return AESGCM


def _derive(master: str, salt: bytes, iterations: int = PBKDF2_ITERATIONS) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", master.encode("utf-8"), salt, iterations, KEY_LEN
    )


class PasswordVault:
    """A master-password-protected store of ``camera_key -> {user, password}``."""

    FILENAME = "vault.enc"

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), self.FILENAME)
        self.auto_path = os.path.join(os.path.dirname(self.path), AUTO_FILENAME)
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self._iterations = PBKDF2_ITERATIONS   # der zum aktuellen _key gehoerige Wert
        self._data: dict[str, dict] = {}

    # --- state --------------------------------------------------------------
    @property
    def exists(self) -> bool:
        return os.path.exists(self.path)

    @property
    def is_locked(self) -> bool:
        return self._key is None

    def _require_unlocked(self) -> None:
        if self.is_locked:
            raise VaultLocked("Tresor ist gesperrt — bitte Master-Passwort eingeben.")

    # --- lifecycle ----------------------------------------------------------
    def create(self, master: str) -> None:
        """Initialise a brand-new vault with the given master password."""
        if self.exists:
            raise VaultError("Tresor existiert bereits.")
        self._salt = os.urandom(SALT_LEN)
        self._iterations = PBKDF2_ITERATIONS
        self._key = _derive(master, self._salt)
        self._data = {}
        self._flush()

    def unlock(self, master: str) -> None:
        """Open an existing vault. Raises VaultError on a wrong password or a
        missing/corrupt vault file (never a raw OSError/JSONDecodeError — die
        Aufrufer fangen gezielt VaultError)."""
        try:
            with open(self.path, encoding="utf-8") as fh:
                blob = json.load(fh)
            if blob.get("kdf", KDF_NAME) != KDF_NAME:
                raise VaultError(f"Unbekanntes Tresor-Verfahren: {blob.get('kdf')}")
            # Gespeicherte Iterationszahl verwenden (nicht die Konstante): so bleiben
            # alte Tresore lesbar, wenn PBKDF2_ITERATIONS spaeter erhoeht wird.
            # Aeltere Dateien ohne Feld wurden mit dem Vorgabewert angelegt.
            iterations = check_iterations(blob.get("iterations", PBKDF2_ITERATIONS))
            salt = base64.b64decode(blob["salt"])
            nonce = base64.b64decode(blob["nonce"])
            ct = base64.b64decode(blob["ct"])
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
            raise VaultError(f"Tresor-Datei nicht lesbar oder beschädigt: {exc}") from exc
        key = _derive(master, salt, iterations)
        try:
            plain = _aesgcm()(key).decrypt(nonce, ct, None)
        except Exception as exc:  # InvalidTag etc. -> wrong password / tampered
            raise VaultError("Falsches Master-Passwort oder beschädigter Tresor.") from exc
        self._salt = salt
        self._iterations = iterations
        self._key = key
        self._data = json.loads(plain.decode("utf-8"))
        if iterations < PBKDF2_ITERATIONS:
            # Schwaecher als die aktuelle Vorgabe -> mit neuem Salt/aktueller
            # Iterationszahl neu verschluesseln (Passwort liegt ja gerade vor).
            try:
                self._salt = os.urandom(SALT_LEN)
                self._iterations = PBKDF2_ITERATIONS
                self._key = _derive(master, self._salt)
                self._flush()
            except OSError:
                pass   # nicht beschreibbar -> Datei bleibt beim alten Stand lesbar

    def lock(self) -> None:
        self._key = None
        self._data = {}

    def change_master(self, old: str, new: str) -> None:
        self.unlock(old)
        self._salt = os.urandom(SALT_LEN)
        self._iterations = PBKDF2_ITERATIONS
        self._key = _derive(new, self._salt)
        self._flush()
        # Auto-Entsperrung (falls aktiv) auf das neue Passwort umschreiben.
        if self.autounlock_enabled:
            self.enable_autounlock(new)

    # --- auto-unlock --------------------------------------------------------
    @property
    def autounlock_enabled(self) -> bool:
        """True, wenn ein Auto-Entsperr-Token hinterlegt ist."""
        return os.path.exists(self.auto_path)

    def enable_autounlock(self, master: str) -> None:
        """Master-Passwort für die Auto-Entsperrung hinterlegen. Verifiziert es
        zuvor durch Entsperren (wirft VaultError bei falschem Passwort)."""
        self.unlock(master)                       # prüft das Passwort
        salt = os.urandom(SALT_LEN)
        nonce = os.urandom(NONCE_LEN)
        secret = _autounlock_secret(os.path.dirname(self.auto_path), create=True)
        ct = _aesgcm()(_machine_key(salt, secret=secret)).encrypt(
            nonce, master.encode("utf-8"), None)
        blob = {
            "version": 1,
            "iterations": AUTO_ITERATIONS,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(),
        }
        tmp = self.auto_path + ".tmp"
        with open_private(tmp) as fh:
            json.dump(blob, fh, indent=2)
        os.replace(tmp, self.auto_path)

    def disable_autounlock(self) -> None:
        """Auto-Entsperr-Token und das zugehörige Per-Install-Geheimnis entfernen."""
        for pfad in (self.auto_path,
                     os.path.join(os.path.dirname(self.auto_path), AUTO_SECRET_FILENAME)):
            try:
                os.remove(pfad)
            except FileNotFoundError:
                pass

    def try_autounlock(self) -> bool:
        """Beim Start aufrufen: entsperrt den Tresor mit dem hinterlegten Token.
        Gibt True bei Erfolg zurück; scheitert still (z. B. anderer Rechner)."""
        if not self.autounlock_enabled or not self.exists:
            return False
        try:
            with open(self.auto_path, encoding="utf-8") as fh:
                blob = json.load(fh)
            iterations = check_iterations(blob.get("iterations", AUTO_ITERATIONS))
            salt = base64.b64decode(blob["salt"])
            nonce = base64.b64decode(blob["nonce"])
            ct = base64.b64decode(blob["ct"])
            secret = _autounlock_secret(os.path.dirname(self.auto_path), create=False)
            master = _aesgcm()(_machine_key(salt, iterations, secret)).decrypt(
                nonce, ct, None).decode("utf-8")
            self.unlock(master)
            return True
        except Exception:  # noqa: BLE001 - Token ungültig/fremder Rechner -> gesperrt bleiben
            return False

    # --- secrets ------------------------------------------------------------
    def set_password(self, camera_key: str, username: str, password: str) -> None:
        self._require_unlocked()
        self._data[camera_key] = {"username": username, "password": password}
        self._flush()

    def set_many(self, items: dict) -> int:
        """Set several entries with a single write. Returns the number stored.

        *items* maps ``camera_key`` -> ``{"username": ..., "password": ...}``.
        Nützlich beim Import vieler Zugangsdaten (statt eines Datei-Writes je Eintrag).
        """
        self._require_unlocked()
        n = 0
        for key, cred in items.items():
            if not key:
                continue
            self._data[key] = {"username": cred.get("username", ""),
                               "password": cred.get("password", "")}
            n += 1
        if n:
            self._flush()
        return n

    def get_password(self, camera_key: str) -> dict | None:
        self._require_unlocked()
        return self._data.get(camera_key)

    def all_entries(self) -> dict:
        """Kopie aller gespeicherten Eintraege (``camera_key -> {username,
        password}``). Erfordert einen entsperrten Tresor."""
        self._require_unlocked()
        return {k: dict(v) for k, v in self._data.items()}

    def delete(self, camera_key: str) -> None:
        self._require_unlocked()
        self._data.pop(camera_key, None)
        self._flush()

    def delete_many(self, camera_keys) -> None:
        """Remove several entries with a single write."""
        self._require_unlocked()
        changed = False
        for key in camera_keys:
            if self._data.pop(key, None) is not None:
                changed = True
        if changed:
            self._flush()

    # --- io -----------------------------------------------------------------
    def _flush(self) -> None:
        self._require_unlocked()
        assert self._salt is not None and self._key is not None
        nonce = os.urandom(NONCE_LEN)
        plain = json.dumps(self._data).encode("utf-8")
        ct = _aesgcm()(self._key).encrypt(nonce, plain, None)
        blob = {
            "version": 1,
            "kdf": KDF_NAME,
            "iterations": self._iterations,
            "cipher": "aes-256-gcm",
            "salt": base64.b64encode(self._salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(),
        }
        tmp = self.path + ".tmp"
        with open_private(tmp) as fh:
            json.dump(blob, fh, indent=2)
        os.replace(tmp, self.path)
