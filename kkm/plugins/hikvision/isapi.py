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

"""Hikvision ISAPI client — stdlib only (urllib/ssl), no vendor SDK.

ISAPI ("Intelligent Security API") is Hikvision's HTTP/REST interface — very close
to Axis' VAPIX: ``GET`` reads, ``PUT``/``POST`` write, bodies are XML under
``/ISAPI/…``, authentication is **HTTP Digest**. As with the Axis plugin, HTTPS is
spoken with an unverified context (the cameras use self-signed certificates).

**Experimental:** the exact XML payloads (esp. SET_IP and USERS) and the reset/
firmware behaviour are modelled on the ISAPI documentation but have **not** been
verified against real hardware yet. Two ISAPI specifics are handled deliberately:

- **Clock-sensitive digest:** a device whose clock drifts more than ~5 minutes
  rejects the digest with 401 — indistinguishable at the HTTP layer from a wrong
  password, so the error text names both possibilities.
- **Account lockout:** five failed logins lock the admin for 30 minutes; the device
  signals this in the response body (``<lockStatus>`` / ``notEnoughPrivilege`` /
  status code ``locked``). :func:`_isapi_error` surfaces that as its own message so
  the caller never blindly retries into a longer lockout.
"""

from __future__ import annotations

import ssl
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from kkm.core import t                 # Uebersetzung, wenn in KKM eingebettet
except Exception:                          # eigenstaendig lauffaehig (stdlib-only)
    def t(s, /, **kw):
        return s.format(**kw) if kw else s

# Hikvision-Geraete nutzen selbstsignierte Zertifikate -> Pruefung aus (wie Axis).
_SSL_CONTEXT = ssl._create_unverified_context()

DEFAULT_PORTS = {"http": 80, "https": 443}
ISAPI = "/ISAPI"


class IsapiError(Exception):
    """Fehler bei einem ISAPI-Aufruf (Netzwerk, Auth oder Geraeteantwort)."""


class IsapiConnectError(IsapiError):
    """Verbindungs-/Netzwerkfehler: Geraet ueber dieses Schema nicht erreichbar.

    Nur dann probiert ``scheme='auto'`` das naechste Schema — bei HTTP-Fehlern
    (401 usw.) hat das Geraet ja geantwortet (vgl. VapixConnectError im Axis-Plugin:
    kein Klartext-Retry ueber HTTP, keine doppelten Fehlversuche Richtung Lockout)."""


# --------------------------------------------------------------------- XML
def _local(tag: str) -> str:
    """Tag ohne Namensraum (ISAPI-Antworten tragen eine Default-Namespace-URI)."""
    return tag.rsplit("}", 1)[-1]


def _find(elem, name: str):
    """Erstes Element mit diesem lokalen Namen (rekursiv), sonst None."""
    if elem is None:
        return None
    for child in elem.iter():
        if _local(child.tag) == name:
            return child
    return None


def _text(elem, name: str, default: str = "") -> str:
    node = _find(elem, name)
    return (node.text or default).strip() if node is not None and node.text else default


def _isapi_error(body: str) -> str:
    """Lesbare Ursache aus einem ISAPI-``ResponseStatus``-Body ziehen.

    ISAPI meldet Fehler als ``<ResponseStatus><statusString>…</statusString>
    <subStatusCode>…</subStatusCode></ResponseStatus>``. Der Lockout nach zu vielen
    Fehlversuchen erscheint als ``subStatusCode`` ``locked``/``userLocked`` bzw.
    ``lockStatus`` — er wird eigens benannt, damit der Aufrufer nicht weiter
    retry-t (was die Sperre nur verlaengert)."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return body.strip()[:200]
    sub = _text(root, "subStatusCode").lower()
    status = _text(root, "statusString") or _text(root, "lockStatus")
    if "lock" in sub or "lock" in status.lower():
        mins = _text(root, "retryLockTime") or _text(root, "lockTime")
        extra = t(" (noch {mins} s gesperrt)", mins=mins) if mins else ""
        return (t("Konto wegen zu vieler Fehlversuche gesperrt") + extra +
                t(" — bitte warten, nicht erneut versuchen."))
    # Der subStatusCode ist oft aussagekraeftiger als der statusString (dieses
    # STD-CGI-OEM meldet z. B. beim Firmware-Upload einer modellfremden Datei den
    # generischen statusString „Invalid XML Content", der wahre Grund steht im
    # subStatusCode „badDevType"). Bekannte Codes klar uebersetzen.
    known = {
        "baddevtype": t("Firmware passt nicht zu diesem Gerätemodell (falscher Gerätetyp)."),
        "badlanguage": t("Firmware hat die falsche Sprachvariante für dieses Gerät."),
        "badversion": t("Firmware-Version wird von diesem Gerät nicht akzeptiert."),
        "notsupport": t("Vom Gerät nicht unterstützt."),
    }
    if sub in known:
        return known[sub]
    return status or sub or t("unbekannter ISAPI-Fehler")


def _check_status(text: str) -> str:
    """Wertet eine ISAPI-``ResponseStatus``-Antwort auf eine Schreib-Aktion aus.

    Erfolg ist ``statusCode == 1`` (bzw. ``statusString`` „OK"); eine **leere**
    Antwort gilt ebenfalls als Erfolg (manche Endpunkte antworten ohne Body). Der
    Sonderfall **„Reboot Required"** (Aenderung uebernommen, wird erst nach Neustart
    wirksam) ist KEIN Fehler — er wird als Hinweistext zurueckgegeben. Alles andere
    wirft :class:`IsapiError` mit lesbarer Ursache (inkl. Lockout, siehe
    :func:`_isapi_error`). An echter STD-CGI-OEM-Hardware verifiziert (das PUT auf
    ``ipAddress`` antwortet dort mit ``statusCode 1`` + „Reboot Required")."""
    if not text.strip():
        return ""
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return ""
    code = _text(root, "statusCode")
    status = _text(root, "statusString")
    sub = _text(root, "subStatusCode").lower()
    if "reboot" in status.lower() or "reboot" in sub:
        return t("Neustart nötig, damit die Änderung wirksam wird")
    if code == "1" or status.lower() == "ok" or sub == "ok":
        return ""
    raise IsapiError(t("Geraet meldete: {body}", body=_isapi_error(text)))


# ------------------------------------------------------------------- HTTP
def _opener(host_port: str, username: str, password: str, auth: bool = True):
    handlers = [urllib.request.HTTPSHandler(context=_SSL_CONTEXT)]
    if auth:
        pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, host_port, username, password)
        handlers = [urllib.request.HTTPDigestAuthHandler(pwmgr),
                    urllib.request.HTTPBasicAuthHandler(pwmgr)] + handlers
    return urllib.request.build_opener(*handlers)


def _request(ip, username, password, path, method="GET", body=None,
             scheme="http", port=None, timeout=10, auth=True,
             content_type="application/xml"):
    """Fuehrt einen ISAPI-Aufruf aus und liefert den Antworttext (str).

    ``body`` wird als *content_type* gesendet — Vorgabe ``application/xml`` (die
    ISAPI-Config-Endpunkte), fuer den **Firmware-Upload** dagegen
    ``application/octet-stream``: eine ``.dav`` als ``application/xml`` zu senden
    beantwortet das Geraet mit HTTP 400 „Invalid XML Content" (an echter Hardware
    verifiziert). Wirft IsapiError bei HTTP-/Auth-Fehlern, IsapiConnectError bei
    Verbindungsfehlern."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    data = body.encode("utf-8") if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": content_type})
    try:
        with _opener(host_port, username, password, auth).open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise IsapiError(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort "
                             "falsch, oder die Uhr der Kamera weicht ab)."))
        try:
            detail = _isapi_error(exc.read().decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 - Body evtl. nicht lesbar
            detail = ""
        raise IsapiError(t("ISAPI-Fehler {code}: {detail}", code=exc.code, detail=detail or exc.reason))
    except urllib.error.URLError as exc:
        raise IsapiConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise IsapiConnectError(t("Verbindungsfehler: {err}", err=exc))


def _request_auto(ip, username, password, path, method="GET", body=None,
                  scheme="auto", port=None, timeout=10, auth=True,
                  content_type="application/xml"):
    """Wie _request; ``auto`` probiert erst HTTPS, dann HTTP — Rueckfall nur bei
    Verbindungsfehlern (nicht bei 401, siehe IsapiConnectError)."""
    if scheme != "auto":
        return _request(ip, username, password, path, method, body, scheme, port,
                        timeout, auth, content_type)
    try:
        return _request(ip, username, password, path, method, body, "https", port,
                        timeout, auth, content_type)
    except IsapiConnectError:
        return _request(ip, username, password, path, method, body, "http", port,
                        timeout, auth, content_type)


def _xml_escape(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


# --------------------------------------------------------------- status/info
def is_online(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn das Geraet per HTTP(S) antwortet. Jede HTTP-Antwort (auch 401)
    zaehlt als online; nur Verbindungs-/Timeout-Fehler gelten als offline."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{ISAPI}/System/deviceInfo"
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
    """Liest Modell, Seriennummer und Firmware (``GET /ISAPI/System/deviceInfo``).

    Liefert ``{model, serial, firmware}``. Wirft IsapiError bei 401 (damit die
    Zugangsdaten-Pruefung im Hauptfenster funktioniert)."""
    text = _request_auto(ip, username, password, f"{ISAPI}/System/deviceInfo",
                         scheme=scheme, port=port, timeout=timeout)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise IsapiError(t("Unlesbare deviceInfo-Antwort: {err}", err=exc))
    return {
        "model": _text(root, "model") or "?",
        "serial": _text(root, "serialNumber") or "?",
        "firmware": _text(root, "firmwareVersion"),
    }


def is_unconfigured(ip, scheme="auto", port=None, timeout=5) -> bool:
    """True, wenn die Kamera noch **inaktiv** (nicht aktiviert) ist.

    Hikvision-Kameras werden ab Werk erst „aktiviert" (Admin-Passwort setzen). Der
    Zustand ist ohne Anmeldung an ``/ISAPI/Security/adminAccesses`` bzw.
    ``userCheck`` ablesbar; hier genuegt der offen lesbare deviceInfo-Endpunkt mit
    ``<activated>`` bzw. der 401-freie Zugriff im Inaktiv-Zustand."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{ISAPI}/System/deviceInfo"
        try:
            with _opener(f"{ip}:{p}", "", "", auth=False).open(url, timeout=timeout) as r:
                body = r.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError:
            return False   # verlangt Auth -> bereits aktiviert
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
        try:
            return _text(ET.fromstring(body), "activated").lower() == "false"
        except ET.ParseError:
            return False
    return False


# ------------------------------------------------------------------- network
def _network_interface_info(ip, username, password, scheme, port, timeout):
    """``(id, ipVersion)`` der ersten Netzwerkschnittstelle (i. d. R. ``1``/``dual``).

    ``ipVersion`` wird beim Setzen der IP **erhalten** — ein Dual-Stack-Geraet
    (``dual``) darf durch ein IPv4-Update nicht ungewollt auf IPv4-only umgestellt
    werden (das schaltete IPv6 ab). An echter Hardware (STD-CGI-OEM) verifiziert."""
    text = _request_auto(ip, username, password, f"{ISAPI}/System/Network/interfaces",
                         scheme=scheme, port=port, timeout=timeout)
    try:
        root = ET.fromstring(text)
        iid = _text(root, "id") or "1"
        ver = _text(root, "ipVersion") or "dual"
    except ET.ParseError:
        iid, ver = "1", "dual"
    return iid, ver


def _ns_of(root) -> str:
    """Namensraum-URI eines geparsten Elements (leer, wenn keiner)."""
    return root.tag[1:root.tag.index("}")] if root.tag.startswith("{") else ""


def _q(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}" if ns else tag


def _set_child(parent, ns: str, tag: str, value: str) -> None:
    """Text eines direkten Kind-Elements setzen (anlegen, falls es fehlt)."""
    node = parent.find(_q(ns, tag))
    if node is None:
        node = ET.SubElement(parent, _q(ns, tag))
    node.text = value


def _read_ip_object(ip, username, password, iface, scheme, port, timeout):
    """Aktuelles ``ipAddress``-Objekt der Schnittstelle lesen -> ``(root, ns)``."""
    text = _request_auto(ip, username, password,
                         f"{ISAPI}/System/Network/interfaces/{iface}/ipAddress",
                         scheme=scheme, port=port, timeout=timeout)
    root = ET.fromstring(text)
    return root, _ns_of(root)


def _put_ip_object(ip, username, password, iface, root, ns, scheme, port, timeout) -> str:
    """Modifiziertes ``ipAddress``-Objekt zurueckschreiben (PUT). Liefert einen
    optionalen Hinweis (z. B. „Neustart nötig")."""
    if ns:
        ET.register_namespace("", ns)   # Default-NS ohne Praefix serialisieren
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            + ET.tostring(root, encoding="unicode"))
    path = f"{ISAPI}/System/Network/interfaces/{iface}/ipAddress"
    text = _request_auto(ip, username, password, path, method="PUT", body=body,
                         scheme=scheme, port=port, timeout=timeout)
    return _check_status(text)


def set_static_ip(ip, username, password, new_ip, subnet_mask, gateway,
                  scheme="auto", port=None, timeout=10):
    """Feste IP setzen. **Read-Modify-Write**: das vollstaendige ``ipAddress``-Objekt
    wird gelesen und nur Adresstyp/IP/Maske/Gateway geaendert — so bleiben IPv6, DNS
    und ``ipVersion`` erhalten und das (aeltere) Geraet akzeptiert das Schema (ein
    minimaler PUT wird mit „Invalid XML Content"/400 abgelehnt; an echter STD-CGI-OEM-
    Hardware verifiziert)."""
    iface, _ = _network_interface_info(ip, username, password, scheme, port, timeout)
    root, ns = _read_ip_object(ip, username, password, iface, scheme, port, timeout)
    _set_child(root, ns, "addressingType", "static")
    _set_child(root, ns, "ipAddress", new_ip)
    _set_child(root, ns, "subnetMask", subnet_mask)
    gw = root.find(_q(ns, "DefaultGateway"))
    if gw is None:
        gw = ET.SubElement(root, _q(ns, "DefaultGateway"))
    _set_child(gw, ns, "ipAddress", gateway)
    hint = _put_ip_object(ip, username, password, iface, root, ns, scheme, port, timeout)
    return t("feste IP {ip} gesetzt", ip=new_ip) + (f" — {hint}" if hint else "")


def set_dhcp(ip, username, password, scheme="auto", port=None, timeout=10):
    """Auf DHCP umstellen (nur ``addressingType`` im vollen Objekt aendern)."""
    iface, _ = _network_interface_info(ip, username, password, scheme, port, timeout)
    root, ns = _read_ip_object(ip, username, password, iface, scheme, port, timeout)
    _set_child(root, ns, "addressingType", "dynamic")
    hint = _put_ip_object(ip, username, password, iface, root, ns, scheme, port, timeout)
    return t("auf DHCP umgestellt") + (f" — {hint}" if hint else "")


# --------------------------------------------------------------------- users
# Hikvision-Rollen: der erste Benutzer (ID 1) ist Administrator; weitere sind
# Operator oder Viewer/„guest". Die Rechte haengen zusaetzlich an userLevel.
USER_ROLES = ("administrator", "operator", "viewer")
_ROLE_TO_LEVEL = {"administrator": "Administrator", "operator": "Operator",
                  "viewer": "Viewer"}


def _users(ip, username, password, scheme, port, timeout) -> list[dict]:
    text = _request_auto(ip, username, password, f"{ISAPI}/Security/users",
                         scheme=scheme, port=port, timeout=timeout)
    out = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return out
    for node in root.iter():
        if _local(node.tag) == "User":
            out.append({"id": _text(node, "id"), "name": _text(node, "userName"),
                        "level": _text(node, "userLevel")})
    return out


def add_user(ip, username, password, new_user, new_password, role="viewer",
             scheme="auto", port=None, timeout=10):
    """Legt einen ISAPI-Benutzer an (``POST /ISAPI/Security/users``)."""
    level = _ROLE_TO_LEVEL.get(role, "Viewer")
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<User xmlns="http://www.hikvision.com/ver20/XMLSchema">'
            f"<userName>{_xml_escape(new_user)}</userName>"
            f"<password>{_xml_escape(new_password)}</password>"
            f"<userLevel>{level}</userLevel></User>")
    text = _request_auto(ip, username, password, f"{ISAPI}/Security/users",
                         method="POST", body=body, scheme=scheme, port=port,
                         timeout=timeout)
    _check_status(text)
    return t("Benutzer '{user}' angelegt ({role})", user=new_user, role=role)


def set_user_password(ip, username, password, target_user, new_password,
                      scheme="auto", port=None, timeout=10):
    """Aendert das Passwort eines bestehenden ISAPI-Benutzers
    (``PUT /ISAPI/Security/users/<id>``). Die Benutzer-ID wird zuvor gelesen."""
    users = _users(ip, username, password, scheme, port, timeout)
    match = next((u for u in users if u["name"] == target_user), None)
    if match is None or not match["id"]:
        raise IsapiError(t("Benutzer '{user}' nicht gefunden.", user=target_user))
    body = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<User xmlns="http://www.hikvision.com/ver20/XMLSchema">'
            f"<id>{_xml_escape(match['id'])}</id>"
            f"<userName>{_xml_escape(target_user)}</userName>"
            f"<password>{_xml_escape(new_password)}</password></User>")
    path = f"{ISAPI}/Security/users/{urllib.parse.quote(match['id'])}"
    text = _request_auto(ip, username, password, path, method="PUT", body=body,
                         scheme=scheme, port=port, timeout=timeout)
    _check_status(text)
    return t("Passwort von '{user}' geaendert", user=target_user)


# ----------------------------------------------------------------- firmware
def upgrade_firmware(ip, username, password, firmware_path, scheme="auto",
                     port=None, timeout=600, factory_default=False):
    """Spielt eine Firmware-Datei auf (``PUT /ISAPI/System/updateFirmware``).

    Hikvision-Firmware ist eine ``digicap.dav``; sie wird als
    ``application/octet-stream`` gesendet — als ``application/xml`` (der Default der
    anderen Endpunkte) antwortet das Geraet mit HTTP 400 „Invalid XML Content" (an
    echter Hardware verifiziert). Das Geraet startet nach dem Upload neu; ein danach
    auftretender Verbindungsfehler ist erwartbar und wird als Erfolg gewertet."""
    with open(firmware_path, "rb") as fh:
        data = fh.read()
    try:
        text = _request_auto(ip, username, password, f"{ISAPI}/System/updateFirmware",
                             method="PUT", body=data, scheme=scheme, port=port,
                             timeout=timeout, content_type="application/octet-stream")
    except IsapiConnectError:
        return t("Firmware hochgeladen — Verbindung getrennt, Geraet flasht/startet neu")
    _check_status(text)
    return t("Firmware aufgespielt — Geraet startet neu")


# ------------------------------------------------------------- factory reset
def factory_reset(ip, username, password, keep_ip=True, scheme="auto", port=None,
                  timeout=30):
    """Werksreset. ``keep_ip=True`` -> ``mode=basic`` (Netzwerk bleibt),
    ``keep_ip=False`` -> ``mode=full``. Das Geraet startet neu."""
    mode = "basic" if keep_ip else "full"
    path = f"{ISAPI}/System/factoryReset?mode={mode}"
    try:
        _request_auto(ip, username, password, path, method="PUT",
                      scheme=scheme, port=port, timeout=timeout)
    except IsapiConnectError:
        pass   # Reboot kappt die Verbindung -> erwartet
    return t("auf Werkseinstellungen zurueckgesetzt") + (
        t(" (IP erhalten)") if keep_ip else t(" (inkl. IP)"))
