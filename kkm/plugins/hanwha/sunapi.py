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

"""Hanwha (Wisenet) SUNAPI client — stdlib only (urllib/ssl), no vendor SDK.

SUNAPI is Hanwha's HTTP-CGI interface under ``/stw-cgi/`` — structurally like Axis
VAPIX / Dahua: ``action=view`` reads, ``action=set``/``add/update``/``control``
writes, responses are ``KEY=VALUE`` lines, authentication is **HTTP Digest**. As with
the other plugins HTTPS is spoken unverified (self-signed certs).

Unlike the earlier feasibility note assumed, the exact endpoints did **not** have to
be guessed: a Wisenet camera documents its own API at
``/stw-cgi/attributes.cgi/<cgi>`` (every submenu/action/parameter with access level).
The endpoints and parameter names below were read from there and verified against a
real QNO-6082R (firmware 1.41.18, 2025). The plugin is still ``experimental`` — only
that one model has been exercised.

Two SUNAPI specifics:

- **Users are fixed slots** (``Users.0`` = admin, ``Users.1..N`` = ``user1..userN``,
  disabled by default). Adding a user = enabling a free slot via
  ``security.cgi?msubmenu=users&action=update&Index=<n>``; there is no free-form
  "create user".
- **Factory reset keeps chosen settings** via ``ExcludeSettings`` (e.g. ``Network``
  to keep the IP) — the ``keep_ip`` equivalent.
"""

from __future__ import annotations

import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    from kkm.core import t                 # Uebersetzung, wenn in KKM eingebettet
except Exception:                          # eigenstaendig lauffaehig (stdlib-only)
    def t(s, /, **kw):
        return s.format(**kw) if kw else s

# Hanwha-Geraete nutzen selbstsignierte Zertifikate -> Pruefung aus (wie Axis/Dahua).
_SSL_CONTEXT = ssl._create_unverified_context()

# Basic-Auth ueber unverschluesseltes HTTP schickt das Passwort im Klartext (ein
# Mithoerer muss nur "Basic" verlangen bzw. Port 443 blockieren). Ab Werk daher nur
# Digest ueber HTTP; per Einstellung abschaltbar -> kkm.plugins.set_basic_over_http().
ALLOW_BASIC_OVER_HTTP = False


class BasicOverHttpRefused(Exception):
    """Gegenstelle verlangt Basic-Auth ueber HTTP — Anmeldung verweigert.

    Bewusst KEIN URLError/OSError: die Upload-Routinen werten Verbindungsfehler als
    "Geraet startet neu" (Erfolg) — diese Ablehnung darf dort nicht verschluckt werden."""


class _BasicAuthHandler(urllib.request.HTTPBasicAuthHandler):
    """HTTPBasicAuthHandler, der ueber ``http://`` keine Zugangsdaten sendet."""

    def __init__(self, password_mgr=None, allow_http=False):
        super().__init__(password_mgr)
        self.allow_http = allow_http

    def http_error_401(self, req, fp, code, msg, headers):
        if req.type == "http" and not (ALLOW_BASIC_OVER_HTTP or self.allow_http):
            schemes = [h.strip().split(" ", 1)[0].lower()
                       for h in headers.get_all("WWW-Authenticate") or []]
            if "digest" in schemes:
                return None   # Digest war schon dran (z. B. falsches Passwort) -> 401
            if "basic" in schemes:
                raise BasicOverHttpRefused(t("Die Kamera verlangt eine Basic-Anmeldung über unverschlüsseltes HTTP (Passwort im Klartext) — abgelehnt. HTTPS verwenden oder unter Einstellungen → Plugins ausdrücklich erlauben."))
        return super().http_error_401(req, fp, code, msg, headers)

DEFAULT_PORTS = {"http": 80, "https": 443}
CGI = "/stw-cgi"


class SunapiError(Exception):
    """Fehler bei einem SUNAPI-Aufruf (Netzwerk, Auth oder Geraeteantwort)."""


class SunapiConnectError(SunapiError):
    """Verbindungs-/Netzwerkfehler: Geraet ueber dieses Schema nicht erreichbar.

    Nur dann probiert ``scheme='auto'`` das naechste Schema — bei HTTP-Fehlern
    (401 usw.) hat das Geraet ja geantwortet (kein Klartext-Retry ueber HTTP)."""


# --------------------------------------------------------------- KEY=VALUE
def _auth_error(msg):
    """401 -> Fehler mit Marker ``auth_failed``, den der GUI-Aktionsdialog erkennt, um das
    Passwort erneut abzufragen (veralteter Tresor-Eintrag nach externer Aenderung)."""
    e = SunapiError(msg)
    e.auth_failed = True
    return e


def _parse_kv(text: str) -> dict:
    """SUNAPIs ``KEY=VALUE``-Zeilen in ein Dict wandeln (wie Axis ``param.cgi``)."""
    out = {}
    for line in text.splitlines():
        line = line.strip().strip('"')
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


# ------------------------------------------------------------------- HTTP
def _opener(host_port: str, username: str, password: str, auth: bool = True):
    handlers = [urllib.request.HTTPSHandler(context=_SSL_CONTEXT)]
    if auth:
        pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, host_port, username, password)
        handlers = [urllib.request.HTTPDigestAuthHandler(pwmgr),
                    _BasicAuthHandler(pwmgr)] + handlers
    return urllib.request.build_opener(*handlers)


# Hanwha antwortet mit HTTP 490, wenn die maximale Zahl gleichzeitiger CGI-Sitzungen
# erreicht ist (z. B. offene Web-UI + Online-Pruefung + Aktion). Das ist transient —
# kurz warten und erneut versuchen, statt die Aktion abzubrechen.
_MAX_490_RETRIES = 3


def _open_read(opener, target, timeout) -> bytes:
    """``opener.open(target)`` + ``read()`` mit Retry bei HTTP 490 („zu viele
    Verbindungen"). ``target`` ist eine URL oder ein ``Request``. Andere HTTP-/
    Verbindungsfehler reicht die Funktion unveraendert an den Aufrufer durch."""
    for attempt in range(_MAX_490_RETRIES + 1):
        try:
            with opener.open(target, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 490 and attempt < _MAX_490_RETRIES:
                time.sleep(1.0 + attempt)   # Session-Slot freiwerden lassen
                continue
            raise


def _request(ip, username, password, path, scheme="http", port=None, timeout=10,
             auth=True):
    """Fuehrt einen SUNAPI-GET-Aufruf aus und liefert den Antworttext (str).

    Wirft SunapiError bei HTTP-/Auth-Fehlern, SunapiConnectError bei
    Verbindungsfehlern."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    try:
        return _open_read(_opener(host_port, username, password, auth), url,
                          timeout).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:  # noqa: BLE001
            detail = ""
        raise SunapiError(t("SUNAPI-Fehler {code}: {detail}", code=exc.code, detail=detail[:160] or exc.reason))
    except urllib.error.URLError as exc:
        raise SunapiConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise SunapiConnectError(t("Verbindungsfehler: {err}", err=exc))


def _request_auto(ip, username, password, path, scheme="auto", port=None, timeout=10,
                  auth=True):
    """Wie _request; ``auto`` probiert erst HTTPS, dann HTTP — Rueckfall nur bei
    Verbindungsfehlern (nicht bei 401, siehe SunapiConnectError)."""
    if scheme != "auto":
        return _request(ip, username, password, path, scheme, port, timeout, auth)
    try:
        return _request(ip, username, password, path, "https", port, timeout, auth)
    except SunapiConnectError:
        return _request(ip, username, password, path, "http", port, timeout, auth)


def _query(params: dict) -> str:
    return "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())


def _check_response(text: str) -> str:
    """SUNAPI quittiert Schreib-Aktionen im **200-Body**: ``OK`` = Erfolg, ``NG`` +
    ``Error Code``/-Meldung = Fehler (der HTTP-Status bleibt 200!). Wirft daher
    SunapiError bei ``NG`` — sonst würden Fehler stumm verschluckt. An echter
    Hardware verifiziert (z. B. ``NG / Error Code: 601 / Action Not Found``)."""
    body = text.strip()
    if body.upper().startswith("NG"):
        code = re.search(r"Error Code:\s*(\d+)", text)
        lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
        msg = lines[-1] if lines else body
        raise SunapiError(t("Geräte-Fehler {code}: {msg}",
                            code=code.group(1) if code else '?', msg=msg))
    return body


# --------------------------------------------------------------- status/info
def is_online(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn das Geraet per HTTP(S) antwortet (jede Antwort inkl. 401 = online)."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{CGI}/system.cgi?msubmenu=deviceinfo&action=view"
        try:
            with _opener(f"{ip}:{p}", "", "", auth=False).open(url, timeout=timeout) as r:
                r.read()
            return True
        except urllib.error.HTTPError:
            return True                       # geantwortet (z. B. 401) -> online
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False


def get_device_info(ip, username, password, scheme="auto", port=None, timeout=10) -> dict:
    """Liest Modell, Seriennummer, Firmware und MAC (``system.cgi deviceinfo``).

    Liefert ``{model, serial, firmware, mac}``. Wirft SunapiError bei 401 (damit die
    Zugangsdaten-Pruefung im Hauptfenster funktioniert)."""
    kv = _parse_kv(_request_auto(
        ip, username, password,
        f"{CGI}/system.cgi?msubmenu=deviceinfo&action=view",
        scheme=scheme, port=port, timeout=timeout))
    return {
        "model": kv.get("Model", "?"),
        "serial": kv.get("SerialNumber", "?"),
        "firmware": kv.get("FirmwareVersion", ""),
        "mac": kv.get("ConnectedMACAddress", ""),
    }


def is_unconfigured(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn die Wisenet noch **nicht initialisiert** ist (werksneu / nach
    Werksreset).

    Solche Kameras blockieren die **gesamte** SUNAPI mit HTTP **403** (ohne
    ``WWW-Authenticate``) — eine bereits initialisierte Kamera verlangt dagegen eine
    Anmeldung (401). Der Unterschied 403↔401 ist das Erkennungsmerkmal (an echter
    Hardware verifiziert). Das Erst-Passwort lässt sich anschliessend **nur über die
    Web-UI** setzen (RSA-verschluesselt), nicht ueber die regulaere API — daher wird
    die Kamera im Hauptfenster als „Ersteinrichtung erforderlich" gefuehrt statt nach
    einem Passwort gefragt."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{CGI}/system.cgi?msubmenu=deviceinfo&action=view"
        try:
            with _opener(f"{ip}:{p}", "", "", auth=False).open(url, timeout=timeout) as r:
                r.read()
            return False   # 200 ohne Auth -> kein Init-Blockade-Fall
        except urllib.error.HTTPError as exc:
            return exc.code == 403   # 403 = uninitialisiert, 401 = bereits initialisiert
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False


# ------------------------------------------------------------------- network
def set_static_ip(ip, username, password, new_ip, subnet_mask, gateway,
                  scheme="auto", port=None, timeout=10):
    """Feste IP setzen (``network.cgi?msubmenu=interface&action=set``).

    ``IPv4Type=Manual`` (Enum: nur ``Manual``/``DHCP``). **Wichtig:**
    ``IPv4PrefixLength`` darf NICHT zusammen mit ``IPv4SubnetMask`` gesendet werden —
    das quittiert die Kamera mit „Invalid Parameter(s)" (602). Maske genuegt (an
    echter Hardware verifiziert)."""
    params = {
        "IPv4Type": "Manual",
        "IPv4Address": new_ip,
        "IPv4SubnetMask": subnet_mask,
    }
    if gateway:
        params["IPv4Gateway"] = gateway
    _check_response(_request_auto(
        ip, username, password,
        f"{CGI}/network.cgi?msubmenu=interface&action=set&{_query(params)}",
        scheme=scheme, port=port, timeout=timeout))
    return t("feste IP {ip} gesetzt", ip=new_ip)


def set_dhcp(ip, username, password, scheme="auto", port=None, timeout=10):
    """Auf DHCP umstellen (``IPv4Type=DHCP``)."""
    _check_response(_request_auto(
        ip, username, password,
        f"{CGI}/network.cgi?msubmenu=interface&action=set&IPv4Type=DHCP",
        scheme=scheme, port=port, timeout=timeout))
    return t("auf DHCP umgestellt")


# --------------------------------------------------------------------- users
# SUNAPI-Benutzer sind feste Slots (Index 0 = admin, 1..N = user1..userN). Die
# Zugriffsrechte sind granular; die Dialog-Rollen werden grob darauf abgebildet.
USER_ROLES = ("administrator", "operator", "viewer")

# add/update-Zugriffsfelder (aus attributes.cgi) je Rolle.
_ACCESS_FIELDS = ("VideoProfileAccess", "AudioInAccess", "AlarmOutputAccess",
                  "VideoProfileSettingAccess", "ImageSettingAccess",
                  "VideoAndFocusSetupAccess")
_ROLE_ACCESS = {
    "administrator": {f: "True" for f in _ACCESS_FIELDS},
    "operator": {"VideoProfileAccess": "True", "AudioInAccess": "True",
                 "AlarmOutputAccess": "True", "VideoProfileSettingAccess": "False",
                 "ImageSettingAccess": "False", "VideoAndFocusSetupAccess": "False"},
    "viewer": {"VideoProfileAccess": "True", "AudioInAccess": "False",
               "AlarmOutputAccess": "False", "VideoProfileSettingAccess": "False",
               "ImageSettingAccess": "False", "VideoAndFocusSetupAccess": "False"},
}


def get_users(ip, username, password, scheme="auto", port=None, timeout=10) -> list[dict]:
    """Liefert die Benutzer-Slots: ``[{index, userid, enabled}]`` (auch leere Slots
    fuer die Slot-Vergabe beim Anlegen)."""
    kv = _parse_kv(_request_auto(
        ip, username, password, f"{CGI}/security.cgi?msubmenu=users&action=view",
        scheme=scheme, port=port, timeout=timeout))
    out = []
    for key, value in kv.items():
        if not key.startswith("Users.") or key == "Users.Index":
            continue
        try:
            idx = int(key.split(".", 1)[1])
        except ValueError:
            continue
        fields = value.split("/")
        userid = fields[0] if fields else ""
        enabled = len(fields) > 2 and fields[2].lower() == "true"
        out.append({"index": idx, "userid": userid, "enabled": enabled})
    return sorted(out, key=lambda u: u["index"])


def add_user(ip, username, password, new_user, new_password, role="viewer",
             scheme="auto", port=None, timeout=10):
    """Aktiviert einen freien Benutzer-Slot (``security.cgi users add/update``).

    Existiert *new_user* bereits, wird sein Slot aktualisiert (Passwort/Rechte),
    sonst der erste freie Slot (Index > 0) belegt."""
    users = get_users(ip, username, password, scheme, port, timeout)
    slot = next((u for u in users if u["userid"] == new_user), None)
    if slot is None:
        # Freie Slots sind **deaktivierte** (Index > 0) — sie tragen ab Werk die
        # Default-Namen user1..userN (nicht etwa eine leere UserID), sind aber
        # ``Enable=False``. An echter Hardware verifiziert.
        slot = next((u for u in users if u["index"] > 0 and not u["enabled"]), None)
    if slot is None:
        raise SunapiError(t("Kein freier Benutzer-Slot verfuegbar (alle belegt)."))
    params = {
        "Index": slot["index"], "UserID": new_user, "Password": new_password,
        "IsPasswordEncrypted": "False", "Enable": "True",
    }
    params.update(_ROLE_ACCESS.get(role, _ROLE_ACCESS["viewer"]))
    _check_response(_request_auto(
        ip, username, password,
        f"{CGI}/security.cgi?msubmenu=users&action=update&{_query(params)}",
        scheme=scheme, port=port, timeout=timeout))
    return t("Benutzer '{user}' angelegt/aktualisiert ({role})", user=new_user, role=role)


def set_user_password(ip, username, password, target_user, new_password,
                      scheme="auto", port=None, timeout=10):
    """Aendert das Passwort eines bestehenden Benutzer-Slots."""
    users = get_users(ip, username, password, scheme, port, timeout)
    slot = next((u for u in users if u["userid"] == target_user), None)
    if slot is None:
        raise SunapiError(t("Benutzer '{user}' nicht gefunden.", user=target_user))
    params = {"Index": slot["index"], "UserID": target_user,
              "Password": new_password, "IsPasswordEncrypted": "False"}
    _check_response(_request_auto(
        ip, username, password,
        f"{CGI}/security.cgi?msubmenu=users&action=update&{_query(params)}",
        scheme=scheme, port=port, timeout=timeout))
    return t("Passwort von '{user}' geaendert", user=target_user)


# ------------------------------------------------------------- factory reset
def factory_reset(ip, username, password, keep_ip=True, scheme="auto", port=None,
                  timeout=30):
    """Werksreset (``system.cgi?msubmenu=factoryreset&action=control``).

    ``keep_ip=True`` -> ``ExcludeSettings=Network`` (Netzwerk bleibt), sonst voller
    Reset. Das Geraet startet neu; ein danach auftretender Verbindungsfehler ist
    erwartbar."""
    path = f"{CGI}/system.cgi?msubmenu=factoryreset&action=control"
    if keep_ip:
        path += "&ExcludeSettings=Network"
    try:
        _request_auto(ip, username, password, path, scheme=scheme, port=port,
                      timeout=timeout)
    except SunapiConnectError:
        pass   # Reboot kappt die Verbindung -> erwartet
    return t("auf Werkseinstellungen zurueckgesetzt") + (
        t(" (IP erhalten)") if keep_ip else t(" (inkl. IP)"))


def reboot(ip, username, password, scheme="auto", port=None, timeout=30):
    """Startet die Kamera neu (``system.cgi?msubmenu=power&action=control&Type=Reboot``)."""
    try:
        _request_auto(ip, username, password,
                      f"{CGI}/system.cgi?msubmenu=power&action=control&Type=Reboot",
                      scheme=scheme, port=port, timeout=timeout)
    except SunapiConnectError:
        pass
    return t("Neustart ausgeloest")


# ----------------------------------------------------------------- firmware
def upgrade_firmware(ip, username, password, firmware_path, scheme="auto",
                     port=None, timeout=600, factory_default=False):
    """Spielt eine Firmware-Datei auf (``system.cgi?msubmenu=firmwareupdate&
    action=control&Type=Normal``), multipart/form-data. Das Geraet startet nach dem
    Upload neu.

    **Wichtig (an echter Hardware verifiziert):** ``Type=Normal`` ist Pflicht (fehlt
    er, antwortet die Kamera mit „Invalid Input Value"); der Multipart-Feldname ist
    egal. Die Antwort ist ein Status-Stream (``Status=DownloadAck/DownloadOK/Start/
    UpdatingISP/End/OK`` bzw. ``Fail``/``Skip``). ``Skip`` = gleiche Version bereits
    installiert. Beim eigentlichen Flashen kappt das Geraet die Verbindung (Reboot) —
    das ist erwartbar und wird als Erfolg gewertet."""
    import os
    with open(firmware_path, "rb") as fh:
        data = fh.read()
    filename = os.path.basename(firmware_path)
    boundary = "----kkmHanwha" + os.urandom(12).hex()
    crlf = b"\r\n"
    body = crlf.join([
        b"--" + boundary.encode(),
        b'Content-Disposition: form-data; name="FirmwareFile"; filename="'
        + filename.encode("utf-8") + b'"',
        b"Content-Type: application/octet-stream", b"", data,
        b"--" + boundary.encode() + b"--", b"",
    ])
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    last_conn = None
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        host_port = f"{ip}:{p}"
        url = (f"{sc}://{host_port}{CGI}/system.cgi"
               "?msubmenu=firmwareupdate&action=control&Type=Normal")
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            text = _open_read(_opener(host_port, username, password), req,
                              timeout).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
            raise SunapiError(t("SUNAPI-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_conn = exc            # Reboot kappt die Verbindung -> erwartet
            continue
        # Status-Stream auswerten
        statuses = re.findall(r"Status=(\w+)", text)
        if any(s.lower() in ("fail", "downloadfail") for s in statuses):
            raise SunapiError(t("Firmware-Update fehlgeschlagen (Status: {status}).",
                              status=', '.join(statuses) or t("unbekannt")))
        if any(s.lower() == "skip" for s in statuses):
            return t("Firmware übersprungen — diese Version ist bereits installiert.")
        return t("Firmware aufgespielt — Gerät startet neu")
    if last_conn is not None:
        return t("Firmware hochgeladen — Verbindung getrennt, Gerät flasht/startet neu")
    raise SunapiConnectError(t("Kamera nicht erreichbar."))


# ------------------------------------------------- Konfigurations-Backup (Blob)
# SUNAPI-Config-Backup: ein opaker, verschluesselter Komplett-Blob (nicht
# auswaehlbar, modell-/firmwaregebunden). Endpunkte aus der Selbstdokumentation
# ``/stw-cgi/attributes.cgi/system`` gelesen und an der QNO-6082R verifiziert:
#   Export  = system.cgi?msubmenu=configbackup&action=control  (liefert den Blob)
#   Restore = system.cgi?msubmenu=configrestore&action=control (Datei hochladen);
#             optional ExcludeSettings=Network -> Netzwerk/IP der Kamera bleibt.
_BACKUP_CGI = "system.cgi?msubmenu=configbackup&action=control"
_RESTORE_CGI = "system.cgi?msubmenu=configrestore&action=control"


def restore_config(ip, username, password, backup_path, keep_network=False,
                   scheme="auto", port=None, timeout=600):
    """Spielt ein Config-Backup ein (``configrestore&action=control``). Mit
    ``keep_network=True`` (``ExcludeSettings=Network``) behaelt die Kamera ihre aktuelle
    IP/Netz-Konfiguration — wichtig, wenn ein Backup auf eine *andere* Kamera gespielt
    wird. Das Geraet startet danach neu; ein Verbindungsabbruch ist erwartbar und wird
    als Erfolg gewertet. ``NG``/``Error Code`` im 200-Body → SunapiError.

    **Format wie die Wisenet-Web-UI (an QNO-6082R V1.41.18 verifiziert):** die rohen
    Datei-Bytes **base64-kodiert** als ``application/x-www-form-urlencoded``-Body — NICHT
    multipart. Ein Multipart-Upload quittiert die Firmware sonst mit ``Error Code 607``.
    (Ermittelt aus dem Web-UI-JavaScript ``/wmf/scripts/customs.js``: ``configRestore``
    → ``btoa(fileBytes)`` + Content-Type ``application/x-www-form-urlencoded``.)"""
    import base64
    with open(backup_path, "rb") as fh:
        data = fh.read()
    body = base64.b64encode(data)
    path = _RESTORE_CGI + ("&ExcludeSettings=Network" if keep_network else "")
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    last_conn = None
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        host_port = f"{ip}:{p}"
        url = f"{sc}://{host_port}{CGI}/{path}"
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded;"})
        try:
            text = _open_read(_opener(host_port, username, password), req,
                              timeout).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
            raise SunapiError(t("SUNAPI-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_conn = exc            # Reboot kappt die Verbindung -> erwartet
            continue
        _check_response(text)          # NG -> SunapiError
        return t("Backup eingespielt — Gerät startet neu")
    if last_conn is not None:
        return t("Backup hochgeladen — Verbindung getrennt, Gerät startet neu")
    raise SunapiConnectError(t("Kamera nicht erreichbar."))


def export_config(ip, username, password, out_path, scheme="auto", port=None,
                  timeout=120):
    """Laedt das aktuelle Config-Backup herunter (``configbackup&action=control``) und
    speichert es unter *out_path*. Fehlerantworten kommen als kurzer Text (``NG``)
    statt Binaerblob → SunapiError."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    last_conn = None
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        host_port = f"{ip}:{p}"
        url = f"{sc}://{host_port}{CGI}/{_BACKUP_CGI}"
        try:
            data = _open_read(_opener(host_port, username, password), url, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
            raise SunapiError(t("SUNAPI-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_conn = exc
            continue
        if data[:16].lstrip()[:2].upper() == b"NG":
            _check_response(data.decode("utf-8", errors="replace"))
        with open(out_path, "wb") as fh:
            fh.write(data)
        return t("Backup gespeichert: {path} ({n} Bytes)", path=out_path, n=len(data))
    if last_conn is not None:
        raise SunapiConnectError(t("Kamera nicht erreichbar: {err}", err=last_conn))
    raise SunapiConnectError(t("Kamera nicht erreichbar."))
