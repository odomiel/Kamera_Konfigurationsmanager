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

from .groups import config_dir

PBKDF2_ITERATIONS = 600_000   # OWASP-recommended floor for PBKDF2-HMAC-SHA256
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


def _getuser() -> str:
    try:
        return getpass.getuser()
    except Exception:  # pragma: no cover - je nach Umgebung
        return "user"


def _machine_key(salt: bytes) -> bytes:
    ident = "\x1f".join([
        platform.node(), _getuser(), platform.system(),
        "kkm-vault-autounlock-v1",
    ])
    return hashlib.pbkdf2_hmac("sha256", ident.encode("utf-8"), salt,
                               AUTO_ITERATIONS, KEY_LEN)


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


def _derive(master: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", master.encode("utf-8"), salt, PBKDF2_ITERATIONS, KEY_LEN
    )


class PasswordVault:
    """A master-password-protected store of ``camera_key -> {user, password}``."""

    FILENAME = "vault.enc"

    def __init__(self, path: str | None = None):
        self.path = path or os.path.join(config_dir(), self.FILENAME)
        self.auto_path = os.path.join(os.path.dirname(self.path), AUTO_FILENAME)
        self._key: bytes | None = None
        self._salt: bytes | None = None
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
            salt = base64.b64decode(blob["salt"])
            nonce = base64.b64decode(blob["nonce"])
            ct = base64.b64decode(blob["ct"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise VaultError(f"Tresor-Datei nicht lesbar oder beschädigt: {exc}") from exc
        key = _derive(master, salt)
        try:
            plain = _aesgcm()(key).decrypt(nonce, ct, None)
        except Exception as exc:  # InvalidTag etc. -> wrong password / tampered
            raise VaultError("Falsches Master-Passwort oder beschädigter Tresor.") from exc
        self._salt = salt
        self._key = key
        self._data = json.loads(plain.decode("utf-8"))

    def lock(self) -> None:
        self._key = None
        self._data = {}

    def change_master(self, old: str, new: str) -> None:
        self.unlock(old)
        self._salt = os.urandom(SALT_LEN)
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
        ct = _aesgcm()(_machine_key(salt)).encrypt(nonce, master.encode("utf-8"), None)
        blob = {
            "version": 1,
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(),
        }
        tmp = self.auto_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=2)
        os.replace(tmp, self.auto_path)

    def disable_autounlock(self) -> None:
        """Auto-Entsperr-Token entfernen."""
        try:
            os.remove(self.auto_path)
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
            salt = base64.b64decode(blob["salt"])
            nonce = base64.b64decode(blob["nonce"])
            ct = base64.b64decode(blob["ct"])
            master = _aesgcm()(_machine_key(salt)).decrypt(nonce, ct, None).decode("utf-8")
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
            "kdf": "pbkdf2-hmac-sha256",
            "iterations": PBKDF2_ITERATIONS,
            "cipher": "aes-256-gcm",
            "salt": base64.b64encode(self._salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(),
        }
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(blob, fh, indent=2)
        os.replace(tmp, self.path)
