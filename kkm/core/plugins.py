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

"""Vendor plugin interface and registry.

A *plugin* encapsulates everything vendor-specific: how to discover devices, read
their info, check whether they are online, and apply settings (IP, users, ONVIF
users, firmware, configuration import/export). The GUI talks only to this
interface, never to a vendor SDK directly — so adding a manufacturer later means
writing one new ``VendorPlugin`` subclass and registering it.

The Axis plugin (:mod:`kkm.plugins.axis.plugin`) implements this by wrapping the
copied VAPIX/discovery modules.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Callable

from . import camera


@dataclass
class Credentials:
    """Admin access data for a camera write operation."""
    username: str = "root"
    password: str = ""
    scheme: str = "auto"          # auto | https | http
    port: int | None = None
    timeout: int = 10


class Capability:
    """Named operations a plugin may support. The GUI greys out unsupported ones."""
    DISCOVER = "discover"
    ONLINE_CHECK = "online_check"
    DEVICE_INFO = "device_info"
    SET_IP = "set_ip"
    USERS = "users"
    ONVIF_USERS = "onvif_users"
    FIRMWARE = "firmware"
    FIRMWARE_CHECK = "firmware_check"   # sucht online nach neuerer Firmware
    CONFIG = "config"
    # Opakes, geraetespezifisches Komplett-Backup (verschluesselter Blob), das nur
    # als Ganzes ein-/ausgespielt wird — im Gegensatz zu CONFIG (auswaehlbare
    # Parameter-Vorlage). Z. B. Hanwha SUNAPI-Config-Backup (.bin).
    CONFIG_BACKUP = "config_backup"
    FACTORY_RESET = "factory_reset"
    TIMEZONE = "timezone"               # Zeitzone setzen (Axis: Time API, IANA)


@dataclass
class FirmwareRelease:
    """Eine herunterladbare Firmware-Version eines Modells."""
    model: str
    version: str
    url: str = ""
    filename: str = ""
    size: int = 0
    notes_url: str = ""


@dataclass
class FirmwareInfo:
    """Ergebnis einer Update-Suche fuer *ein* Modell."""
    model: str
    current: str = ""
    versions: list[str] = field(default_factory=list)  # neueste zuerst
    latest: str = ""                                   # neueste ueberhaupt
    recommended: str = ""                              # Vorschlag ("" = kein Update)


# A progress callback receives (ip, ok, message) per camera for live result logs.
ProgressFn = Callable[[str, bool, str], None]


class VendorPlugin(abc.ABC):
    """Base class for all manufacturer plugins."""

    #: stable identifier used in settings/persistence, e.g. "axis"
    id: str = ""
    #: human-readable name shown in the plugin manager
    name: str = ""
    #: set of Capability.* this plugin implements
    capabilities: set[str] = set()
    #: True fuer herstellerneutrale Plugins (ONVIF): sie finden auch Geraete, fuer
    #: die es ein spezialisiertes Plugin gibt. Die Suche im Hauptfenster verwirft
    #: darum generische Treffer, deren IP ein Hersteller-Plugin schon gemeldet hat —
    #: sonst stuende dieselbe Kamera zweimal in der Liste.
    generic: bool = False

    #: True fuer noch nicht an echter Hardware verifizierte Plugins. Der
    #: Plugin-Manager kennzeichnet sie als „experimentell"; sie sind ab Werk aus.
    experimental: bool = False

    #: True, wenn ``import_config_backup`` das Erhalten der Netzwerk-/IP-Einstellungen
    #: unterstuetzt (Hanwha ``ExcludeSettings=Network``). Der Backup-Dialog blendet die
    #: Checkbox „Netz behalten" nur dann ein. Standard: nicht unterstuetzt.
    config_backup_keep_network: bool = False

    #: True, wenn das Einspielen eines Backups an echter Hardware verifiziert ist. Ist
    #: es False, zeigt der Backup-Dialog einen Warnhinweis „noch nicht verifiziert".
    config_backup_import_verified: bool = False

    #: Dateiendungen der Firmware-Datei im Firmware-Dialog (Datei-Auswahl). Herstellerspezifisch
    #: (Axis/Dahua ``.bin``, Hikvision ``.dav``, Hanwha/Wisenet ``.img``). Der Firmware-Dialog
    #: baut daraus den Dateifilter für das jeweilige Modell.
    firmware_extensions: tuple[str, ...] = (".bin",)

    #: Dateiendung und Anzeigename der Backup-Datei im Datei-Dialog. Herstellerspezifisch
    #: (verschluesselter ``.bin``-Blob bei Hikvision/Hanwha/Dahua, ``.json``-Ressourcen-
    #: Map bei Axis). Der Backup-Dialog baut daraus den Dateifilter.
    config_backup_extension: str = ".bin"
    config_backup_filetype_label: str = "Backup"

    #: Optionale Einspiel-Varianten ``(wert, beschriftung)`` — z. B. Axis „merge"/
    #: „default". Ist die Liste leer, zeigt der Dialog keine Auswahl und uebergibt
    #: ``import_mode=None`` (das Plugin waehlt seinen Standard).
    config_backup_import_modes: tuple[tuple[str, str], ...] = ()

    #: Werksseitiger Standard-Benutzername des Herstellers. Der Zugangsdaten-Block der
    #: Aktionsdialoge belegt das Benutzerfeld damit vor (Axis „root", die meisten
    #: anderen „admin") — sonst schlaegt jede Aktion an einer Nicht-Axis-Kamera mit 401
    #: fehl, weil „root" dort nicht existiert.
    default_username: str = "root"

    #: Rollen des Benutzer-Dialogs bzw. Stufen des ONVIF-Dialogs, hoechstes Recht
    #: zuerst. Die Dialoge lesen sie vom Plugin — sie sind herstellerabhaengig.
    USER_ROLES: tuple[str, ...] = ()
    ONVIF_LEVELS: tuple[str, ...] = ()

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def is_auth_error(self, exc: Exception) -> bool:
        """True, wenn *exc* eine fehlgeschlagene Authentifizierung (HTTP 401) ist — dann
        bietet der Aktionsdialog eine erneute Passwortabfrage an. Die stdlib-Clients
        markieren solche Fehler mit dem Attribut ``auth_failed`` (i18n-sicher, ohne auf
        die uebersetzte Meldung zu matchen); Plugins mit anderer Fehlerquelle ueberschreiben."""
        return bool(getattr(exc, "auth_failed", False))

    # --- neutrale Helfer (Plugins duerfen ueberschreiben) --------------------
    def parse_user_list(self, path, onvif: bool = False):
        """Benutzerliste ``Name,Passwort[,Rolle]`` fuer den Stapel-Import lesen.
        Validiert gegen die Rollen/Stufen *dieses* Plugins."""
        roles = self.ONVIF_LEVELS if onvif else self.USER_ROLES
        if not roles:
            raise NotImplementedError
        return camera.parse_user_list(path, roles, roles[-1])   # niedrigster Rang

    # --- configuration files (Capability.CONFIG) ----------------------------
    # Format und Aufbau der Konfigurationsdatei sind herstellerspezifisch; die GUI
    # kennt sie nicht und ruft nur diese drei Methoden auf.
    def parse_config_file(self, path) -> dict:
        """Konfigurationsdatei einlesen/pruefen (wirft bei ungueltiger Datei)."""
        raise NotImplementedError

    def write_config_file(self, path, config: dict, selected_params=None,
                          with_profiles: bool = True, with_vmd4: bool = True,
                          selected_profiles=None):
        """Gelesene Konfiguration als Datei schreiben (Auswahl der Parameter)."""
        raise NotImplementedError

    def import_config(self, camera: dict, creds: Credentials, cfg_path,
                      selected_params=None, selected_profiles=None,
                      with_vmd4: bool = True):
        """Konfigurationsdatei auf eine Kamera anwenden. Die Auswahl-Argumente
        spiegeln :meth:`write_config_file` — was sich exportieren laesst, laesst sich
        auch gezielt importieren (``None`` = alles)."""
        raise NotImplementedError

    # --- opaque config backup (Capability.CONFIG_BACKUP) --------------------
    # Manche Hersteller (Hanwha, Hikvision, Dahua) bieten nur ein verschluesseltes
    # Komplett-Backup an — nicht auswaehlbar, geraete-/modellgebunden. Getrennt von
    # CONFIG (Parameter-Vorlage), damit die GUI beides sauber unterscheidet.
    def import_config_backup(self, camera: dict, creds: Credentials, backup_path,
                             keep_network: bool = False, import_mode: str | None = None,
                             progress: "ProgressFn | None" = None) -> str:
        """Spielt ein zuvor gesichertes Komplett-Backup (opaker Blob) auf die Kamera
        ein. Mit ``keep_network`` bleiben IP-/Netzwerkeinstellungen der Zielkamera
        erhalten (wichtig beim Einspielen auf eine *andere* Kamera). ``import_mode``
        waehlt eine herstellerspezifische Einspiel-Variante (siehe
        ``config_backup_import_modes``; ``None`` = Plugin-Standard). Das Geraet startet
        danach i. d. R. neu. Nur verfuegbar, wenn das Plugin ``Capability.CONFIG_BACKUP``
        meldet."""
        raise NotImplementedError

    def export_config_backup(self, camera: dict, creds: Credentials, out_path) -> str:
        """Laedt das aktuelle Komplett-Backup der Kamera herunter und speichert es
        unter *out_path*. Optionaler Gegenpart zu :meth:`import_config_backup`."""
        raise NotImplementedError

    # --- Zeitzone (Capability.TIMEZONE) -------------------------------------
    # Herstellerspezifisch (Axis: Time API mit IANA-Namen). Die Auswahlliste im Dialog
    # kommt aus der stdlib (``zoneinfo``); ``get_timezone`` dient dem Anzeigen/Uebernehmen
    # der aktuell gesetzten Zone.
    def set_timezone(self, camera: dict, creds: Credentials, timezone: str) -> str:
        """Setzt die Zeitzone der Kamera (IANA-Name, z. B. ``Europe/Berlin``)."""
        raise NotImplementedError

    def get_timezone(self, camera: dict, creds: Credentials) -> str:
        """Liest die aktuell gesetzte Zeitzone (IANA-Name; leer, wenn unbekannt)."""
        raise NotImplementedError

    def list_timezones(self, camera: dict, creds: Credentials) -> list[str]:
        """Vom Geraet unterstuetzte IANA-Zeitzonen; leer, wenn nicht abrufbar (der Dialog
        faellt dann auf die stdlib-Liste zurueck). Optional — Standard: leer."""
        return []

    # --- discovery & status -------------------------------------------------
    @abc.abstractmethod
    def discover(self, timeout: int = 10) -> list[dict]:
        """Scan the LAN and return camera dicts (must include the base fields)."""

    @abc.abstractmethod
    def check_online(self, camera: dict, creds: Credentials | None = None) -> bool:
        """Return True if the camera currently answers."""

    def device_info(self, camera: dict, creds: Credentials) -> dict:
        """Read extended info (model, firmware, serial). Optional."""
        raise NotImplementedError

    def is_unconfigured(self, camera: dict, creds: Credentials | None = None) -> bool:
        """True, wenn sich die Kamera noch im Auslieferungszustand befindet (kein
        Passwort gesetzt, Ersteinrichtung nötig). Optional; Standard: False."""
        return False

    def factory_reset(self, camera: dict, creds: Credentials, keep_ip: bool = True):
        """Setzt die Kamera auf Werkseinstellungen zurück. ``keep_ip`` erhält die
        Netzwerk-/IP-Einstellungen. Nur verfügbar, wenn das Plugin
        ``Capability.FACTORY_RESET`` meldet."""
        raise NotImplementedError

    # --- firmware lookup (Capability.FIRMWARE_CHECK) ------------------------
    # Der Hersteller-Download ist Plugin-Sache: welche Versionen es fuer ein Modell
    # gibt, wo sie liegen und wie eine Version verglichen wird, weiss nur das Plugin.
    # Die GUI reicht das Ergebnis nur an den bestehenden Firmware-Upload weiter.
    def firmware_updates(self, model: str, current: str = "",
                         prefer_track: bool = True) -> FirmwareInfo:
        """Sucht online nach Firmware fuer *model* und vergleicht mit *current*."""
        raise NotImplementedError

    def firmware_release(self, model: str, version: str = "") -> FirmwareRelease:
        """Download-Daten einer Version (leer = neueste)."""
        raise NotImplementedError

    def download_firmware(self, release: FirmwareRelease, progress=None,
                          cancelled=None) -> str:
        """Laedt die Firmware herunter (Cache) und liefert den lokalen Pfad.
        ``progress(done, total)`` laeuft im Worker-Thread."""
        raise NotImplementedError

    def firmware_cache_size(self) -> int:
        """Belegter Platz der heruntergeladenen Firmware (Bytes)."""
        return 0

    def clear_firmware_cache(self) -> None:
        """Heruntergeladene Firmware verwerfen."""

    # --- configuration actions ---------------------------------------------
    # These mirror the Discovery tool's "Kameraeinstellungen" tabs, which become
    # front-view toolbar buttons. Each acts on the selected cameras; per-camera
    # outcomes are reported via ``progress``. Concrete signatures are defined by
    # the plugin; the GUI dialogs are wired up centrally in ``gui/dialogs`` via
    # the ``ACTION_DIALOGS`` map (Capability.* -> Toplevel dialog class).


@dataclass
class PluginRegistry:
    """Holds available plugins and their enabled/disabled state."""
    _plugins: dict[str, VendorPlugin] = field(default_factory=dict)
    _enabled: set[str] = field(default_factory=set)

    def register(self, plugin: VendorPlugin, enabled: bool = True) -> None:
        self._plugins[plugin.id] = plugin
        if enabled:
            self._enabled.add(plugin.id)

    def all(self) -> list[VendorPlugin]:
        return list(self._plugins.values())

    def enabled(self) -> list[VendorPlugin]:
        return [p for pid, p in self._plugins.items() if pid in self._enabled]

    def get(self, plugin_id: str) -> VendorPlugin | None:
        return self._plugins.get(plugin_id)

    def is_enabled(self, plugin_id: str) -> bool:
        return plugin_id in self._enabled

    def set_enabled(self, plugin_id: str, enabled: bool) -> None:
        if plugin_id not in self._plugins:
            return
        if enabled:
            self._enabled.add(plugin_id)
        else:
            self._enabled.discard(plugin_id)

    def enabled_ids(self) -> list[str]:
        return sorted(self._enabled)
