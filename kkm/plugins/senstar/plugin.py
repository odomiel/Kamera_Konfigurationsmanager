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

"""Senstar (Aimetis) Thin Client plugin.

The Thin Client (e.g. A10D) is a network **video decoder**, not a camera: it receives
ONVIF Profile S / RTSP streams and shows them on a monitor. It is therefore *not* an
ONVIF **server** - the generic ONVIF plugin cannot see or manage it (verified on
hardware: WS-Discovery does not find it, ``/onvif/device_service`` serves only the web
UI). This dedicated plugin makes it appear in the device list and configures its
network.

``DISCOVER`` / ``ONLINE_CHECK`` work unauthenticated via the device's 404-page
fingerprint (no login). ``DEVICE_INFO``, ``SET_IP`` (``POST /Settings``, read-modify-
write), ``FACTORY_RESET`` (``GET /System/Restore``), ``USERS`` (``/User``) and
``FIRMWARE`` (``.bin`` via ``PUT /System/Update`` + ``POST /System/Update/FromFile``,
polling ``GET /System/Update/State`` for the ``ExitCode``) all use the token login
(``POST /Session`` ``{user,pwd}`` -> ``Data.Token`` -> cookie ``authtoken``), mapped
from the device's ``server.js`` and verified against an A10D (every write path live,
including a real firmware flash 3.10.0.2726 -> 3.13.1.3293). ``VIDEO_SOURCES`` im-/
exports the device's list of video sources (``GET /Camera/Export`` ->
``POST /import.html`` with the multipart field ``camerasFile``; the hidden
``returnCode`` 0 means success) — the same ``cameras-<ts>.json`` the web UI offers.
There is no ``FIRMWARE_CHECK``: Senstar firmware lives behind the xnet login (no public
download URL for an in-app auto-download); the device updates itself online instead. The
plugin is ``experimental`` and shipped off by default.
"""

from __future__ import annotations

from kkm.core.camera import get_first_ip
from kkm.core.plugins import VendorPlugin, Credentials, Capability
from . import discovery
from . import session


class SenstarPlugin(VendorPlugin):
    id = "senstar"
    name = "Senstar Thin Client"
    #: Decoder, keine Kamera; noch nicht in jedem Schreibpfad an Hardware verifiziert.
    experimental = True
    default_username = "admin"
    capabilities = {
        Capability.DISCOVER,
        Capability.ONLINE_CHECK,
        Capability.DEVICE_INFO,
        Capability.SET_IP,
        Capability.USERS,
        Capability.FIRMWARE,
        Capability.FACTORY_RESET,
        Capability.VIDEO_SOURCES,
    }
    #: Benutzerrollen (hoechstes Recht zuerst) — der Benutzer-Dialog liest sie hier.
    USER_ROLES = ("admin", "viewer")
    #: Firmware-Datei des Thin Clients (z. B. A10D_<version>_Firmware.bin).
    firmware_extensions = (".bin",)
    #: Dateityp der Videoquellen-Liste (Camera-Export) — vom Videoquellen-Dialog gelesen.
    video_sources_extension = ".json"
    video_sources_filetype_label = "Videoquellen"

    def is_auth_error(self, exc: Exception) -> bool:
        return bool(getattr(exc, "auth_failed", False))

    # --- helpers ------------------------------------------------------------
    @staticmethod
    def _mac_aus_serial(serial: str) -> str:
        """Die Geräte-Seriennummer des Thin Client IST seine MAC-Adresse (die
        Hardware basiert auf Lanner, OUI 00:90:0B) — z. B. ``00900B587DA2`` ->
        ``00:90:0B:58:7D:A2``. Als MAC formatieren, wenn es 12 Hex-Ziffern sind;
        sonst unverändert als Seriennummer zurückgeben."""
        s = (serial or "").strip().replace(":", "").replace("-", "")
        if len(s) == 12 and all(c in "0123456789abcdefABCDEF" for c in s):
            return ":".join(s[i:i + 2] for i in range(0, 12, 2)).upper()
        return (serial or "").strip()

    @staticmethod
    def _ip(camera: dict) -> str:
        ip = get_first_ip(camera)
        if not ip:
            raise session.SenstarError("Gerät hat keine IP-Adresse.")
        return ip

    def _anmelden(self, ip: str, creds: Credentials) -> str:
        benutzer = creds.username or self.default_username
        return session.anmelden(ip, benutzer, creds.password,
                                timeout=min(creds.timeout, 10))

    # --- discovery & status -------------------------------------------------
    def discover(self, timeout: int = 10) -> list[dict]:
        cams = discovery.suche(timeout=timeout)
        for cam in cams:
            cam["_vendor"] = self.id
        return cams

    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        ip = get_first_ip(camera)
        if not ip:
            return False
        # Unauthentifizierter Fingerprint als Lebenszeichen (kein Loginversuch).
        try:
            return session.kennung(ip, timeout=5) is not None
        except Exception:  # noqa: BLE001 - offline ist kein Fehlerfall
            return False

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        """Modell + Softwarefassung. Mit Zugangsdaten exakt aus ``/Settings``
        (FirmwareVersion); ohne — bzw. wenn der Login scheitert — aus der
        unauthentifizierten 404-Kennung."""
        ip = get_first_ip(camera)
        if not ip:
            return {}
        info = session.kennung(ip, timeout=6) or {}
        modell = info.get("modell", "")
        version = info.get("version", "")
        mac = ""
        if creds and creds.password:
            try:
                token = self._anmelden(ip, creds)
                try:
                    werte = {e["Name"]: e["Value"]
                             for e in session.einstellungen_lesen(ip, token, creds.timeout)}
                finally:
                    session.abmelden(ip, token)
                version = werte.get("FirmwareVersion", version)
                # Die MAC/Seriennummer liefert der unauth. Fingerprint nicht —
                # sie steht nur authentifiziert in /Settings (DeviceSerial).
                mac = self._mac_aus_serial(werte.get("DeviceSerial", ""))
            except session.SenstarError:
                pass   # Fingerprint-Werte bleiben
        ergebnis = {"model": modell, "firmware": version}
        if mac:
            ergebnis["mac"] = mac
        return ergebnis

    # --- actions ------------------------------------------------------------
    def set_static_ip(self, camera, creds: Credentials, new_ip, mask, gateway):
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.einstellungen_schreiben(ip, token, {
                "NetworkMode": "static",
                "NetworkIP": new_ip,
                "NetworkMask": mask,
                "NetworkGW": gateway or "",
            }, timeout=max(creds.timeout, 15))
        finally:
            session.abmelden(ip, token)

    def set_dhcp(self, camera, creds: Credentials):
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.einstellungen_schreiben(ip, token, {"NetworkMode": "dhcp"},
                                            timeout=max(creds.timeout, 15))
        finally:
            session.abmelden(ip, token)

    def factory_reset(self, camera, creds: Credentials, keep_ip: bool = True):
        # Der Thin Client kennt nur einen vollen Restore (kein „IP behalten").
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.werksreset(ip, token, timeout=max(creds.timeout, 15))
        finally:
            session.abmelden(ip, token)

    # --- Benutzer (Capability.USERS) ----------------------------------------
    def add_user(self, camera, creds: Credentials, new_user, new_password,
                 role="viewer", factory=False):
        # Der Thin Client hat keinen Werks-/Erstbenutzer-Fluss ueber die API —
        # 'factory' ist hier ohne Wirkung (ein Admin-Login ist immer noetig).
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.benutzer_anlegen(ip, token, new_user, new_password,
                                     admin=(role == "admin"),
                                     timeout=max(creds.timeout, 10))
        finally:
            session.abmelden(ip, token)
        return f"Benutzer '{new_user}' angelegt (Rolle {role})"

    def set_user_password(self, camera, creds: Credentials, target_user, new_password):
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.benutzer_passwort(ip, token, target_user, new_password,
                                      timeout=max(creds.timeout, 10))
        finally:
            session.abmelden(ip, token)
        return f"Passwort von '{target_user}' geändert"

    # --- Firmware (Capability.FIRMWARE) -------------------------------------
    def upgrade_firmware(self, camera, creds: Credentials, firmware_path,
                         factory_default=False):
        """Spielt eine Firmware-Datei ein (``PUT /System/Update`` +
        ``POST /System/Update/FromFile``) und wartet auf den Abschluss. Das Geraet
        startet danach neu. ``factory_default`` hat beim Thin Client keine Wirkung."""
        import time
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.firmware_einspielen(ip, token, firmware_path)
            # Auf den Abschluss warten: ExitCode gesetzt = fertig; wird das Geraet
            # durch den Neustart unerreichbar, gilt das Einspielen als angestossen.
            frist = time.time() + 900          # bis 15 min (Installation + Neustart)
            letzter = ""
            while time.time() < frist:
                time.sleep(5)
                try:
                    st = session.firmware_status(ip, token)
                except session.SenstarError:
                    break                      # Neustart -> Session/Netz weg
                letzter = st.get("Progress") or letzter
                code = st.get("ExitCode")
                if code is not None:
                    if code == 0:
                        return "Firmware eingespielt, Gerät startet neu."
                    raise session.SenstarError(
                        f"Firmware-Update fehlgeschlagen (ExitCode {code}).")
            return ("Firmware hochgeladen und angewandt; Gerät startet neu "
                    f"(Status: {letzter or 'unbekannt'}).")
        finally:
            session.abmelden(ip, token)

    # --- Videoquellen (Capability.VIDEO_SOURCES) ----------------------------
    def export_video_sources(self, camera, creds: Credentials, path):
        """Lädt die Videoquellen-Liste des Geräts herunter und speichert sie als
        Datei (``GET /Camera/Export``). Die Datei enthält die Zugangsdaten der
        Quellen im Klartext — darauf weist der Dialog hin."""
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            daten = session.videoquellen_export(ip, token,
                                                timeout=max(creds.timeout, 20))
        finally:
            session.abmelden(ip, token)
        with open(path, "wb") as datei:
            datei.write(daten)
        return f"Videoquellen exportiert ({len(daten)} Byte)"

    def import_video_sources(self, camera, creds: Credentials, path):
        """Spielt eine Videoquellen-Datei ein (``POST /import.html``). Der Import ist
        additiv/mergend (Abgleich über die Quellen-Id), kein Ersetzen."""
        with open(path, "rb") as datei:
            daten = datei.read()
        ip = self._ip(camera)
        token = self._anmelden(ip, creds)
        try:
            session.videoquellen_import(ip, token, daten,
                                        timeout=max(creds.timeout, 60))
        finally:
            session.abmelden(ip, token)
        return "Videoquellen eingespielt"
