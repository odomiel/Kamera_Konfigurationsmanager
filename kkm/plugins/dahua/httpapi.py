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

"""Dahua HTTP API client — stdlib only (urllib/ssl), no vendor SDK.

The Dahua HTTP API is CGI-based under ``/cgi-bin/…`` — structurally between Axis
VAPIX and Hikvision ISAPI: ``?action=getConfig`` reads, ``?action=setConfig`` writes,
responses are ``KEY=VALUE`` lines (like Axis ``param.cgi``), authentication is **HTTP
Digest**. As with the other plugins HTTPS is spoken unverified (self-signed certs).

**Experimental:** the exact ``setConfig`` field names and the firmware/reset behaviour
follow the (semi-public) Dahua HTTP API documentation but have **not** been verified
against real hardware. Two Dahua specifics are handled like in the Hikvision plugin:

- **Clock-sensitive digest / lockout:** drift or too many failed logins → 401 or an
  ``Error``/lock body; :func:`_dahua_error` names the lockout so the caller does not
  blindly retry into a longer lock.
- **Connection-only fallback:** ``scheme='auto'`` retries HTTP only on
  :class:`DahuaConnectError` (never on 401 — no plaintext credential retry).
"""

from __future__ import annotations

import os
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request

try:
    from kkm.core import t                 # Uebersetzung, wenn in KKM eingebettet
except Exception:                          # eigenstaendig lauffaehig (stdlib-only)
    def t(s, /, **kw):
        return s.format(**kw) if kw else s

# Dahua-Geraete nutzen selbstsignierte Zertifikate -> Pruefung aus (wie Axis/Hikvision).
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
CGI = "/cgi-bin"


class DahuaError(Exception):
    """Fehler bei einem Dahua-HTTP-API-Aufruf (Netzwerk, Auth oder Geraeteantwort)."""


class DahuaConnectError(DahuaError):
    """Verbindungs-/Netzwerkfehler: Geraet ueber dieses Schema nicht erreichbar.

    Nur dann probiert ``scheme='auto'`` das naechste Schema — bei HTTP-Fehlern
    (401 usw.) hat das Geraet ja geantwortet (kein Klartext-Retry ueber HTTP, keine
    doppelten Fehlversuche Richtung Lockout — vgl. VapixConnectError/IsapiConnectError)."""


# --------------------------------------------------------------- KEY=VALUE
def _auth_error(msg):
    """401 -> Fehler mit Marker ``auth_failed``, den der GUI-Aktionsdialog erkennt, um das
    Passwort erneut abzufragen (veralteter Tresor-Eintrag nach externer Aenderung)."""
    e = DahuaError(msg)
    e.auth_failed = True
    return e


def _parse_kv(text: str) -> dict:
    """Dahuas ``KEY=VALUE``-Zeilen in ein Dict wandeln (wie Axis ``param.cgi``)."""
    out = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def _kv_value(params: dict, suffix: str) -> str:
    """Wert unabhaengig vom Praefix (``table.``/``root.``): Dahua liefert je nach
    Aufruf ``table.Network.eth0.IPAddress`` oder blank ``IPAddress``."""
    suffix = suffix.lower()
    for key, value in params.items():
        if key.lower().endswith(suffix):
            return value
    return ""


def _dahua_error(body: str) -> str:
    """Lesbare Ursache aus einer Dahua-Fehlerantwort ziehen.

    Dahua meldet Fehler als Klartext (``Error``/``error: …``); ein Konto-Lockout
    erscheint als ``locked``/``blocked``/``UserLocked`` — der wird eigens benannt,
    damit der Aufrufer nicht weiter retry-t (was die Sperre verlaengert)."""
    low = body.lower()
    if "lock" in low or "blocked" in low:
        return t("Konto wegen zu vieler Fehlversuche gesperrt — bitte warten, "
                 "nicht erneut versuchen.")
    m = re.search(r"error\s*:?\s*(.+)", body, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:200]
    return body.strip()[:200] or t("unbekannter Dahua-Fehler")


# ------------------------------------------------------------------- HTTP
def _opener(host_port: str, username: str, password: str, auth: bool = True):
    handlers = [urllib.request.HTTPSHandler(context=_SSL_CONTEXT)]
    if auth:
        pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, host_port, username, password)
        handlers = [urllib.request.HTTPDigestAuthHandler(pwmgr),
                    _BasicAuthHandler(pwmgr)] + handlers
    return urllib.request.build_opener(*handlers)


def _request(ip, username, password, path, scheme="http", port=None, timeout=10,
             auth=True):
    """Fuehrt einen GET-Aufruf aus und liefert den Antworttext (str).

    Wirft DahuaError bei HTTP-/Auth-Fehlern, DahuaConnectError bei Verbindungsfehlern."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    try:
        with _opener(host_port, username, password, auth).open(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort "
                             "falsch, oder die Uhr der Kamera weicht ab)."))
        try:
            detail = _dahua_error(exc.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 - Body evtl. nicht lesbar
            detail = ""
        raise DahuaError(t("Dahua-Fehler {code}: {detail}", code=exc.code, detail=detail or exc.reason))
    except urllib.error.URLError as exc:
        raise DahuaConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise DahuaConnectError(t("Verbindungsfehler: {err}", err=exc))


def _request_auto(ip, username, password, path, scheme="auto", port=None, timeout=10,
                  auth=True):
    """Wie _request; ``auto`` probiert erst HTTPS, dann HTTP — Rueckfall nur bei
    Verbindungsfehlern (nicht bei 401, siehe DahuaConnectError)."""
    if scheme != "auto":
        return _request(ip, username, password, path, scheme, port, timeout, auth)
    try:
        return _request(ip, username, password, path, "https", port, timeout, auth)
    except DahuaConnectError:
        return _request(ip, username, password, path, "http", port, timeout, auth)


def _check_ok(text: str) -> None:
    """Dahua antwortet auf erfolgreiche Schreib-Aktionen mit ``OK``; alles andere
    (``Error``, leere/abweichende Antwort) ist ein Fehler."""
    if "OK" not in text and "ok" not in text.lower():
        raise DahuaError(t("Geraet meldete: {body}", body=_dahua_error(text)))


# --------------------------------------------------------------- status/info
def is_online(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn das Geraet per HTTP(S) antwortet (jede Antwort inkl. 401 = online)."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{CGI}/magicBox.cgi?action=getDeviceType"
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
    """Liest Modell, Seriennummer und Firmware ueber ``magicBox.cgi``.

    Liefert ``{model, serial, firmware}``. Wirft DahuaError bei 401 (damit die
    Zugangsdaten-Pruefung im Hauptfenster funktioniert)."""
    dev = _parse_kv(_request_auto(ip, username, password,
                                  f"{CGI}/magicBox.cgi?action=getDeviceType",
                                  scheme=scheme, port=port, timeout=timeout))
    model = _kv_value(dev, "type") or "?"
    # Seriennummer und Firmware ergaenzend (schlucken Lesefehler bis auf 401 oben).
    serial = firmware = ""
    try:
        sn = _parse_kv(_request_auto(ip, username, password,
                                     f"{CGI}/magicBox.cgi?action=getSerialNo",
                                     scheme=scheme, port=port, timeout=timeout))
        serial = _kv_value(sn, "sn")
    except DahuaError:
        pass
    try:
        sw = _parse_kv(_request_auto(ip, username, password,
                                     f"{CGI}/magicBox.cgi?action=getSoftwareVersion",
                                     scheme=scheme, port=port, timeout=timeout))
        firmware = _kv_value(sw, "version")
    except DahuaError:
        pass
    return {"model": model, "serial": serial or "?", "firmware": firmware}


def is_unconfigured(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn die Kamera noch **inaktiv** (nicht initialisiert) ist.

    Neuere Dahua-Geraete verlangen wie Hikvision zuerst ein Admin-Passwort. Heuristik
    wie beim Axis-Plugin: liefert ein unauthentifizierter, sonst geschuetzter Aufruf
    HTTP 200, ist noch kein Passwort gesetzt."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{CGI}/magicBox.cgi?action=getMachineName"
        try:
            with _opener(f"{ip}:{p}", "", "", auth=False).open(url, timeout=timeout) as r:
                r.read()
            return True                       # 200 ohne Auth -> nicht initialisiert
        except urllib.error.HTTPError:
            return False                      # verlangt Auth -> bereits initialisiert
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return False


# ------------------------------------------------------------------- network
def set_static_ip(ip, username, password, new_ip, subnet_mask, gateway,
                  scheme="auto", port=None, timeout=10):
    """Feste IP setzen (``configManager.cgi?action=setConfig&Network.eth0.…``)."""
    params = {
        "Network.eth0.DhcpEnable": "false",
        "Network.eth0.IPAddress": new_ip,
        "Network.eth0.SubnetMask": subnet_mask,
    }
    if gateway:
        params["Network.eth0.DefaultGateway"] = gateway
    query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    text = _request_auto(ip, username, password,
                         f"{CGI}/configManager.cgi?action=setConfig&{query}",
                         scheme=scheme, port=port, timeout=timeout)
    _check_ok(text)
    return t("feste IP {ip} gesetzt", ip=new_ip)


def set_dhcp(ip, username, password, scheme="auto", port=None, timeout=10):
    """Auf DHCP umstellen (``Network.eth0.DhcpEnable=true``)."""
    text = _request_auto(
        ip, username, password,
        f"{CGI}/configManager.cgi?action=setConfig&Network.eth0.DhcpEnable=true",
        scheme=scheme, port=port, timeout=timeout)
    _check_ok(text)
    return t("auf DHCP umgestellt")


# --------------------------------------------------------------------- users
# Dahua-Gruppen: "admin" (Vollzugriff) oder "user". Rollen des Dialogs darauf abbilden.
USER_ROLES = ("administrator", "operator", "viewer")
_ROLE_TO_GROUP = {"administrator": "admin", "operator": "user", "viewer": "user"}


def add_user(ip, username, password, new_user, new_password, role="viewer",
             scheme="auto", port=None, timeout=10):
    """Legt einen Benutzer an (``userManager.cgi?action=addUser&user.…``)."""
    group = _ROLE_TO_GROUP.get(role, "user")
    params = {
        "user.Name": new_user,
        "user.Password": new_password,
        "user.Group": group,
        "user.Sharable": "true",
        "user.Reserved": "false",
        "user.Memo": "kkm",
    }
    query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    text = _request_auto(ip, username, password,
                         f"{CGI}/userManager.cgi?action=addUser&{query}",
                         scheme=scheme, port=port, timeout=timeout)
    _check_ok(text)
    return t("Benutzer '{user}' angelegt ({role})", user=new_user, role=role)


def set_user_password(ip, username, password, target_user, new_password,
                      scheme="auto", port=None, timeout=10):
    """Aendert das Passwort eines Benutzers (als Admin ueber ``modifyUser``)."""
    params = {"name": target_user, "user.Password": new_password}
    query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    text = _request_auto(ip, username, password,
                         f"{CGI}/userManager.cgi?action=modifyUser&{query}",
                         scheme=scheme, port=port, timeout=timeout)
    _check_ok(text)
    return t("Passwort von '{user}' geaendert", user=target_user)


# ----------------------------------------------------------------- firmware
def _multipart_body(filename: str, data: bytes):
    """Baut einen multipart/form-data-Body (ein Datei-Feld ``file``)."""
    boundary = "----DahuaKKM" + os.urandom(12).hex()
    bb = boundary.encode("ascii")
    crlf = b"\r\n"
    buf = [
        b"--" + bb,
        b'Content-Disposition: form-data; name="file"; filename="'
        + filename.encode("utf-8") + b'"',
        b"Content-Type: application/octet-stream",
        b"",
        data,
        b"--" + bb + b"--",
        b"",
    ]
    return crlf.join(buf), boundary


def upgrade_firmware(ip, username, password, firmware_path, scheme="auto",
                     port=None, timeout=600, factory_default=False):
    """Spielt eine Firmware-Datei auf (``POST /cgi-bin/upgrade.cgi?action=doUpgrade``).

    Das Geraet startet nach dem Upload neu; ein danach auftretender Verbindungsfehler
    ist erwartbar und wird als Erfolg gewertet."""
    with open(firmware_path, "rb") as fh:
        data = fh.read()
    filename = os.path.basename(firmware_path)
    body, boundary = _multipart_body(filename, data)
    path = f"{CGI}/upgrade.cgi?action=doUpgrade"

    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    last_conn_err = None
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        host_port = f"{ip}:{p}"
        url = f"{sc}://{host_port}{path}"
        req = urllib.request.Request(
            url, data=body, method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with _opener(host_port, username, password).open(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="replace")
            _check_ok(text)
            return t("Firmware aufgespielt — Geraet startet neu")
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
            raise DahuaError(t("Dahua-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_conn_err = exc            # Reboot kappt die Verbindung -> erwartet
            continue
    if last_conn_err is not None:
        return t("Firmware hochgeladen — Verbindung getrennt, Geraet flasht/startet neu")
    raise DahuaConnectError(t("Kamera nicht erreichbar."))


# ------------------------------------------------------------- factory reset
def factory_reset(ip, username, password, keep_ip=True, scheme="auto", port=None,
                  timeout=30):
    """Werksreset. ``keep_ip=True`` -> ``restoreExcept&names[0]=Network`` (Netzwerk
    bleibt), sonst ``restore`` (alles). Danach Neustart (best effort)."""
    if keep_ip:
        action = "restoreExcept&names[0]=Network"
    else:
        action = "restore"
    try:
        text = _request_auto(ip, username, password,
                             f"{CGI}/configManager.cgi?action={action}",
                             scheme=scheme, port=port, timeout=timeout)
        _check_ok(text)
    except DahuaConnectError:
        pass   # manche Geraete rebooten sofort -> Verbindungsabbruch erwartet
    # Neustart anstossen (schluckt Verbindungsabbruch durch den Reboot).
    try:
        _request_auto(ip, username, password, f"{CGI}/magicBox.cgi?action=reboot",
                      scheme=scheme, port=port, timeout=min(timeout, 10))
    except DahuaError:
        pass
    return t("auf Werkseinstellungen zurueckgesetzt") + (
        t(" (IP erhalten)") if keep_ip else t(" (inkl. IP)"))
