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

"""ONVIF Device Management client — stdlib only, no vendor SDK.

Everything the generic plugin can do goes through *one* SOAP endpoint, the device
service (``http://<ip>/onvif/device_service``): device info, users, network
interfaces, factory default. Video/media services are deliberately absent — this
program configures cameras, it does not watch them.

**Authentication** is WS-Security ``UsernameToken`` with a password digest,
``Base64(SHA1(nonce + created + password))``. The catch is ``created``: the device
rejects the token if the timestamp is far from *its own* clock. So every
authenticated call is preceded (once per device) by ``GetSystemDateAndTime``, which
the spec allows without authentication, and the resulting offset is applied — that is
the difference between "works" and an unexplained 401 on a camera whose clock drifted.
HTTP digest/basic credentials are sent alongside, because some devices want those
instead.

Cameras use self-signed certificates, so HTTPS here is unverified — same as the Axis
plugin. (Unlike the firmware download, which pulls a foreign file off the internet and
therefore *does* verify.)
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import os
import http.client
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

try:
    from kkm.core import t                 # Uebersetzung, wenn in KKM eingebettet
except Exception:                          # eigenstaendig lauffaehig (stdlib-only)
    def t(s, /, **kw):
        return s.format(**kw) if kw else s

DEVICE_PATH = "/onvif/device_service"
DEFAULT_PORTS = {"http": 80, "https": 443}

# Kameras haben meist selbstsignierte Zertifikate -> Pruefung aus (wie im Axis-Plugin).
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
                raise BasicOverHttpRefused(t("Die Kamera verlangt eine Basic-Anmeldung über unverschlüsseltes HTTP (Passwort im Klartext) — abgelehnt. HTTPS verwenden oder unter Einstellungen → Verbindungssicherheit ausdrücklich erlauben."))
        return super().http_error_401(req, fp, code, msg, headers)


# Connect-Hook fuer die Zertifikatspruefung (Trust-on-First-Use), gesetzt von
# kkm.plugins.set_connect_hook(): ``hook(scheme, host, port, der)``. Aufgerufen
# direkt nach dem TLS-Handshake (der = DER-Zertifikat), nach einem gescheiterten
# HTTPS-Aufbau (der = None) und vor jedem HTTP-Aufbau. Wirft der Hook, wird die
# Verbindung verworfen, BEVOR eine Anfrage (und damit ein Passwort) gesendet wird.
CONNECT_HOOK = None


class _HookedHTTPSConnection(http.client.HTTPSConnection):
    def connect(self):
        hook = CONNECT_HOOK
        try:
            super().connect()
        except OSError:
            if hook is not None:
                hook("https", self.host, self.port, None)
            raise
        if hook is not None:
            try:
                hook("https", self.host, self.port, self.sock.getpeercert(binary_form=True))
            except BaseException:
                self.close()
                raise


class _HookedHTTPConnection(http.client.HTTPConnection):
    def connect(self):
        if CONNECT_HOOK is not None:
            CONNECT_HOOK("http", self.host, self.port, None)
        super().connect()


class _HookedHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_HookedHTTPSConnection, req, context=self._context)


class _HookedHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(_HookedHTTPConnection, req)

_ENVELOPE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
    ' xmlns:tds="http://www.onvif.org/ver10/device/wsdl"'
    ' xmlns:tt="http://www.onvif.org/ver10/schema">'
    "{header}<s:Body>{body}</s:Body></s:Envelope>"
)
_WSSE = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd"
_WSU = "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-utility-1.0.xsd"
_PW_DIGEST = ("http://docs.oasis-open.org/wss/2004/01/"
              "oasis-200401-wss-username-token-profile-1.0#PasswordDigest")
_B64 = ("http://docs.oasis-open.org/wss/2004/01/"
        "oasis-200401-wss-soap-message-security-1.0#Base64Binary")


class OnvifError(Exception):
    """Fehler bei einem ONVIF-Aufruf (Netzwerk, Auth oder Geraeteantwort)."""


# --------------------------------------------------------------------- XML
def _auth_error(msg):
    """401 -> Fehler mit Marker ``auth_failed``, den der GUI-Aktionsdialog erkennt, um das
    Passwort erneut abzufragen (veralteter Tresor-Eintrag nach externer Aenderung)."""
    e = OnvifError(msg)
    e.auth_failed = True
    return e


def _local(tag: str) -> str:
    """Tag ohne Namensraum — ONVIF-Geraete nutzen wechselnde Praefixe."""
    return tag.rsplit("}", 1)[-1]


def _find(elem, name: str):
    """Erstes Element mit diesem lokalen Namen (rekursiv), sonst None."""
    for child in elem.iter():
        if _local(child.tag) == name:
            return child
    return None


def _text(elem, name: str, default: str = "") -> str:
    node = _find(elem, name) if elem is not None else None
    return (node.text or default).strip() if node is not None and node.text else default


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def _fault(root) -> str:
    """Lesbaren Text aus einem SOAP-Fault ziehen (leer, wenn keiner drin ist)."""
    if _find(root, "Fault") is None:
        return ""
    for name in ("Text", "faultstring"):
        node = _find(root, name)
        if node is not None and node.text:
            return node.text.strip()
    return "unbekannter SOAP-Fehler"


# ------------------------------------------------------------------- HTTP
def device_url(ip: str, scheme: str = "http", port: int | None = None,
               xaddr: str = "") -> str:
    """Endpunkt des Device-Service. Ein per WS-Discovery gemeldetes XAddr gewinnt —
    manche Geraete haengen ihn an einen abweichenden Pfad oder Port."""
    if xaddr:
        return xaddr
    scheme = "http" if scheme not in ("http", "https") else scheme
    p = port or DEFAULT_PORTS[scheme]
    return f"{scheme}://{ip}:{p}{DEVICE_PATH}"


def _opener(url: str, username: str, password: str):
    handlers = [_HookedHTTPSHandler(context=_SSL_CONTEXT), _HookedHTTPHandler()]
    if username:
        pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        pwmgr.add_password(None, url, username, password)
        handlers = [urllib.request.HTTPDigestAuthHandler(pwmgr),
                    _BasicAuthHandler(pwmgr)] + handlers
    return urllib.request.build_opener(*handlers)


def _security_header(username: str, password: str, offset: timedelta) -> str:
    """WS-Security UsernameToken. *offset* verschiebt ``Created`` auf die Uhr der
    Kamera — ohne das scheitert die Anmeldung bei abweichender Geraetezeit."""
    nonce = os.urandom(16)
    created = (datetime.now(timezone.utc) + offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    digest = hashlib.sha1(nonce + created.encode() + password.encode()).digest()
    return (
        f'<s:Header><Security xmlns="{_WSSE}" s:mustUnderstand="1"><UsernameToken>'
        f"<Username>{_escape(username)}</Username>"
        f'<Password Type="{_PW_DIGEST}">{base64.b64encode(digest).decode()}</Password>'
        f'<Nonce EncodingType="{_B64}">{base64.b64encode(nonce).decode()}</Nonce>'
        f'<Created xmlns="{_WSU}">{created}</Created>'
        "</UsernameToken></Security></s:Header>"
    )


def call(url: str, body: str, username: str = "", password: str = "",
         offset: timedelta = timedelta(0), timeout: int = 10):
    """Einen SOAP-Aufruf absetzen und den geparsten Body-Baum liefern.

    Ohne *username* unauthentifiziert (nur GetSystemDateAndTime braucht das).
    """
    header = _security_header(username, password, offset) if username else ""
    data = _ENVELOPE.format(header=header, body=body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": 'application/soap+xml; charset=utf-8'})
    try:
        with _opener(url, username, password).open(req, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            reason = _fault(ET.fromstring(detail))
        except ET.ParseError:
            reason = ""
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen — ONVIF-Benutzer/"
                             "Passwort falsch, oder die Uhr der Kamera weicht ab."))
        raise OnvifError(reason or t("HTTP {code}: {reason}", code=exc.code, reason=exc.reason)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise OnvifError(t("Nicht erreichbar: {err}", err=exc)) from exc

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise OnvifError(t("Unlesbare Antwort: {err}", err=exc)) from exc
    reason = _fault(root)
    if reason:
        raise OnvifError(t("ONVIF-Fehler: {reason}", reason=reason))
    return root


# --------------------------------------------------------------- Operationen
def system_time(url: str, timeout: int = 5) -> datetime | None:
    """UTC-Zeit der Kamera (``GetSystemDateAndTime``) — laut Spec ohne Anmeldung.
    Dient zugleich als Erreichbarkeitspruefung."""
    root = call(url, "<tds:GetSystemDateAndTime/>", timeout=timeout)
    utc = _find(root, "UTCDateTime")
    if utc is None:
        return None
    date, time_ = _find(utc, "Date"), _find(utc, "Time")
    if date is None or time_ is None:
        return None
    try:
        return datetime(
            int(_text(date, "Year")), int(_text(date, "Month")), int(_text(date, "Day")),
            int(_text(time_, "Hour")), int(_text(time_, "Minute")),
            int(_text(time_, "Second")), tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def time_offset(url: str, timeout: int = 5) -> timedelta:
    """Versatz zwischen Kamera- und lokaler Uhr (fuer den UsernameToken)."""
    device_now = system_time(url, timeout)
    if device_now is None:
        return timedelta(0)
    return device_now - datetime.now(timezone.utc)


def device_information(url, username, password, offset, timeout=10) -> dict:
    root = call(url, "<tds:GetDeviceInformation/>", username, password, offset, timeout)
    return {
        "manufacturer": _text(root, "Manufacturer"),
        "model": _text(root, "Model") or "?",
        "firmware": _text(root, "FirmwareVersion"),
        "serial": _text(root, "SerialNumber") or "?",
        "hardware": _text(root, "HardwareId"),
    }


def get_users(url, username, password, offset, timeout=10) -> list[dict]:
    root = call(url, "<tds:GetUsers/>", username, password, offset, timeout)
    users = []
    for node in root.iter():
        if _local(node.tag) == "User":
            users.append({"name": _text(node, "Username"),
                          "level": _text(node, "UserLevel")})
    return users


def create_user(url, username, password, offset, new_user, new_password,
                level="Administrator", timeout=10) -> str:
    body = ("<tds:CreateUsers><tds:User>"
            f"<tt:Username>{_escape(new_user)}</tt:Username>"
            f"<tt:Password>{_escape(new_password)}</tt:Password>"
            f"<tt:UserLevel>{_escape(level)}</tt:UserLevel>"
            "</tds:User></tds:CreateUsers>")
    call(url, body, username, password, offset, timeout)
    return t("ONVIF-Benutzer '{user}' angelegt ({level})", user=new_user, level=level)


def set_user(url, username, password, offset, target_user, new_password,
             level="Administrator", timeout=10) -> str:
    body = ("<tds:SetUser><tds:User>"
            f"<tt:Username>{_escape(target_user)}</tt:Username>"
            f"<tt:Password>{_escape(new_password)}</tt:Password>"
            f"<tt:UserLevel>{_escape(level)}</tt:UserLevel>"
            "</tds:User></tds:SetUser>")
    call(url, body, username, password, offset, timeout)
    return t("ONVIF-Passwort von '{user}' geändert", user=target_user)


def network_interfaces(url, username, password, offset, timeout=10) -> list[dict]:
    """Netzwerkschnittstellen mit ihrem Token (den braucht SetNetworkInterfaces)."""
    root = call(url, "<tds:GetNetworkInterfaces/>", username, password, offset, timeout)
    out = []
    for node in root.iter():
        if _local(node.tag) != "NetworkInterfaces":
            continue
        info = _find(node, "Info")
        ipv4 = _find(node, "IPv4")
        cfg = _find(ipv4, "Config") if ipv4 is not None else None
        addr = _find(cfg, "Manual") if cfg is not None else None
        out.append({
            "token": node.get("token", ""),
            "name": _text(info, "Name") if info is not None else "",
            "mac": _text(info, "HwAddress") if info is not None else "",
            "dhcp": (_text(cfg, "DHCP").lower() == "true") if cfg is not None else False,
            "address": _text(addr, "Address") if addr is not None else "",
        })
    return out


def _prefix_len(mask: str) -> int:
    """Subnetzmaske -> Praefixlaenge; ONVIF rechnet in Praefixen, die GUI in Masken."""
    mask = (mask or "").strip()
    if mask.isdigit():
        return int(mask)
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{mask}").prefixlen
    except ValueError as exc:
        raise OnvifError(t("Ungültige Subnetzmaske: {mask}", mask=mask)) from exc


def set_static_ip(url, username, password, offset, token, new_ip, mask,
                  gateway="", timeout=10) -> str:
    prefix = _prefix_len(mask)
    body = (f'<tds:SetNetworkInterfaces><tds:InterfaceToken>{_escape(token)}'
            "</tds:InterfaceToken><tds:NetworkInterface>"
            "<tt:Enabled>true</tt:Enabled><tt:IPv4><tt:Enabled>true</tt:Enabled>"
            "<tt:Manual>"
            f"<tt:Address>{_escape(new_ip)}</tt:Address>"
            f"<tt:PrefixLength>{prefix}</tt:PrefixLength>"
            "</tt:Manual><tt:DHCP>false</tt:DHCP></tt:IPv4>"
            "</tds:NetworkInterface></tds:SetNetworkInterfaces>")
    root = call(url, body, username, password, offset, timeout)
    reboot = _text(root, "RebootNeeded").lower() == "true"
    if gateway:
        # Eigene Operation — SetNetworkInterfaces kennt kein Gateway.
        gw_body = ("<tds:SetNetworkDefaultGateway>"
                   f"<tds:IPv4Address>{_escape(gateway)}</tds:IPv4Address>"
                   "</tds:SetNetworkDefaultGateway>")
        call(url, gw_body, username, password, offset, timeout)
    msg = t("IP auf {ip}/{prefix} gesetzt", ip=new_ip, prefix=prefix)
    return msg + (t(" — Neustart nötig") if reboot else "")


def set_dhcp(url, username, password, offset, token, timeout=10) -> str:
    body = (f'<tds:SetNetworkInterfaces><tds:InterfaceToken>{_escape(token)}'
            "</tds:InterfaceToken><tds:NetworkInterface>"
            "<tt:Enabled>true</tt:Enabled><tt:IPv4><tt:Enabled>true</tt:Enabled>"
            "<tt:DHCP>true</tt:DHCP></tt:IPv4>"
            "</tds:NetworkInterface></tds:SetNetworkInterfaces>")
    root = call(url, body, username, password, offset, timeout)
    reboot = _text(root, "RebootNeeded").lower() == "true"
    return t("auf DHCP umgestellt") + (t(" — Neustart nötig") if reboot else "")


def factory_default(url, username, password, offset, hard=False, timeout=10) -> str:
    """``Soft`` behaelt die Netzwerkeinstellungen, ``Hard`` setzt alles zurueck."""
    kind = "Hard" if hard else "Soft"
    body = f"<tds:SetSystemFactoryDefault><tds:FactoryDefault>{kind}" \
           "</tds:FactoryDefault></tds:SetSystemFactoryDefault>"
    call(url, body, username, password, offset, timeout)
    return t("auf Werkseinstellungen zurückgesetzt ({kind})", kind=kind)
