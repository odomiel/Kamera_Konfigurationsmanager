# Axis_Kamera_Discovery - VAPIX-Client zum Aendern von Kamera-Einstellungen.
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

"""Kommunikation mit Axis-Kameras ueber die VAPIX-HTTP-API.

Nutzt nur die Standardbibliothek (urllib/ssl/hashlib), damit im AppImage keine
weiteren Pakete noetig sind. HTTPS wird mit einem ungeprueften SSL-Kontext
gesprochen, weil Axis-Geraete in der Regel selbstsignierte Zertifikate nutzen.
Authentifizierung per HTTP-Digest (mit Basic als Rueckfall).
"""

import csv
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

try:
    from kkm.core import t                 # Uebersetzung, wenn in KKM eingebettet
except Exception:                          # eigenstaendig lauffaehig (stdlib-only)
    def t(s, /, **kw):
        return s.format(**kw) if kw else s

# Axis-Geraete haben meist selbstsignierte Zertifikate -> Zertifikatspruefung aus.
_SSL_CONTEXT = ssl._create_unverified_context()

# Standard-Ports je Schema
DEFAULT_PORTS = {"http": 80, "https": 443}


class VapixError(Exception):
    """Fehler bei einem VAPIX-Aufruf (Netzwerk, Auth oder Geraeteantwort)."""


class VapixConnectError(VapixError):
    """Verbindungs-/Netzwerkfehler: das Geraet war ueber dieses Schema gar nicht
    erreichbar. NUR dann probiert 'auto' das naechste Schema — bei HTTP-Fehlern
    (z. B. 401) hat das Geraet ja geantwortet, ein Wechsel auf HTTP wuerde die
    Zugangsdaten unnoetig im Klartext wiederholen und Fehlversuche verdoppeln
    (Brute-Force-Sperre des Geraets)."""


def _auth_error(msg):
    """401 -> Fehler mit Marker ``auth_failed``, den der GUI-Aktionsdialog erkennt, um das
    Passwort erneut abzufragen (z. B. wenn es ausserhalb des Programms geaendert wurde und
    der Tresor-Eintrag veraltet ist)."""
    e = VapixError(msg)
    e.auth_failed = True
    return e


def _build_opener(host_port, username, password, auth=True):
    """Opener mit ungepruefter HTTPS-Verbindung.

    Mit auth=True zusaetzlich Digest-/Basic-Auth; mit auth=False ganz ohne
    Authentifizierung (fuer werksneue Geraete ohne gesetztes Passwort).
    """
    handlers = [urllib.request.HTTPSHandler(context=_SSL_CONTEXT)]
    if auth:
        pwmgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        # Realm None -> gilt fuer alle; URL ohne Schema deckt http und https ab.
        pwmgr.add_password(None, host_port, username, password)
        handlers = [
            urllib.request.HTTPDigestAuthHandler(pwmgr),
            urllib.request.HTTPBasicAuthHandler(pwmgr),
        ] + handlers
    return urllib.request.build_opener(*handlers)


def _request(ip, username, password, path, scheme="http", port=None, timeout=10, auth=True):
    """Fuehrt einen GET-Aufruf aus und liefert den Antworttext (str).

    Wirft VapixError bei Netzwerk-/Auth-/HTTP-Fehlern. Mit auth=False ohne
    Authentifizierung (werksneue Geraete).
    """
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    opener = _build_opener(host_port, username, password, auth=auth)
    try:
        with opener.open(url, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        raise VapixError(t("HTTP-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
    except urllib.error.URLError as exc:
        raise VapixConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise VapixConnectError(t("Verbindungsfehler: {err}", err=exc))


def _request_auto(ip, username, password, path, scheme="auto", port=None, timeout=10, auth=True):
    """Wie _request, aber 'auto' probiert erst HTTPS, dann HTTP.

    Der Rueckfall auf HTTP greift NUR bei Verbindungsfehlern (HTTPS-Port zu o. Ae.)
    — nicht bei HTTP-Fehlern wie 401, siehe VapixConnectError."""
    if scheme != "auto":
        return _request(ip, username, password, path, scheme, port, timeout, auth)
    try:
        return _request(ip, username, password, path, "https", port, timeout, auth)
    except VapixConnectError:
        return _request(ip, username, password, path, "http", port, timeout, auth)


def _post_form(ip, username, password, path, fields, scheme, port, timeout):
    """POSTet x-www-form-urlencoded und liefert den Antworttext."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    body = urllib.parse.urlencode(fields).encode("utf-8")
    opener = _build_opener(host_port, username, password)
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        raise VapixError(t("HTTP-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
    except urllib.error.URLError as exc:
        raise VapixConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise VapixConnectError(t("Verbindungsfehler: {err}", err=exc))


def _post_form_auto(ip, username, password, path, fields, scheme="auto", port=None, timeout=30):
    """Wie _post_form, aber 'auto' probiert erst HTTPS, dann HTTP (Rueckfall nur
    bei Verbindungsfehlern, siehe VapixConnectError)."""
    if scheme != "auto":
        return _post_form(ip, username, password, path, fields, scheme, port, timeout)
    try:
        return _post_form(ip, username, password, path, fields, "https", port, timeout)
    except VapixConnectError:
        return _post_form(ip, username, password, path, fields, "http", port, timeout)


def _http_error_detail(exc) -> str:
    """Liefert eine kurze, lesbare Ursache aus dem Body einer HTTPError-Antwort.

    AXIS-JSON-APIs betten die eigentliche Fehlermeldung meist als JSON
    (``error.message``) oder Klartext in den Body ein — auch bei HTTP 500.
    """
    try:
        raw = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:  # noqa: BLE001 - Body evtl. nicht lesbar
        return ""
    if not raw:
        return ""
    try:
        data = json.loads(raw)
    except ValueError:
        return raw[:200]
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or err.get("code") or err)[:200]
    if err:
        return str(err)[:200]
    return raw[:200]


def _post_json(ip, username, password, path, obj, scheme, port, timeout, method="POST"):
    """Sendet einen JSON-Body (POST oder PATCH) und liefert die geparste Antwort (Dict).

    Fuer die JSON-Steuer-APIs neuerer AXIS-Funktionen (z. B. VMD4) und die
    Device-Configuration-API (``$import`` per PATCH). Leere Antworten ergeben ``{}``;
    nicht-JSON-Antworten werfen VapixError.
    """
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    body = json.dumps(obj).encode("utf-8")
    opener = _build_opener(host_port, username, password)
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
        method=method)
    try:
        with opener.open(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        # AXIS-JSON-APIs liefern die eigentliche Ursache oft im Fehler-Body mit --
        # unbedingt anzeigen (z. B. bei 500 vom VMD4-control.cgi).
        detail = _http_error_detail(exc)
        raise VapixError(t("HTTP-Fehler {code}: {reason}", code=exc.code, reason=exc.reason)
                         + (f" — {detail}" if detail else ""))
    except urllib.error.URLError as exc:
        raise VapixConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise VapixConnectError(t("Verbindungsfehler: {err}", err=exc))
    if not text.strip():
        return {}
    try:
        return json.loads(text)
    except ValueError:
        raise VapixError(t("Unerwartete Antwort: {body}", body=text.strip()[:200]))


def _post_json_auto(ip, username, password, path, obj, scheme="auto", port=None,
                    timeout=30, method="POST"):
    """Wie _post_json, aber 'auto' probiert erst HTTPS, dann HTTP (Rueckfall nur
    bei Verbindungsfehlern, siehe VapixConnectError)."""
    if scheme != "auto":
        return _post_json(ip, username, password, path, obj, scheme, port, timeout, method)
    try:
        return _post_json(ip, username, password, path, obj, "https", port, timeout, method)
    except VapixConnectError:
        return _post_json(ip, username, password, path, obj, "http", port, timeout, method)


def _is_setup_response(exc) -> bool:
    """Erkennt an einer 401-Antwort von ``pwdgrp.cgi``, ob das Geraet noch die
    Ersteinrichtung verlangt (AXIS-OS-Werkszustand).

    AXIS OS 10/11 verlangt auch werksneu eine Authentifizierung, kennzeichnet den
    Setup-Zustand aber ueber den Antwort-Header ``axis-setup: vapix`` bzw. den Body
    ``Error: initial admin user must be created first.`` — im Gegensatz zum
    normalen Digest-Challenge eines bereits konfigurierten Geraets.
    """
    try:
        if exc.headers is not None and exc.headers.get("axis-setup"):
            return True
    except Exception:  # noqa: BLE001 - defensiv, Header duerfen fehlen
        pass
    try:
        body = exc.read().decode("utf-8", errors="replace").lower()
    except Exception:  # noqa: BLE001 - Body evtl. nicht lesbar
        return False
    return "initial admin user must be created" in body


# Werksseitige Standard-Zugangsdaten aelterer AXIS-Geraete. Werden ausschliesslich
# zur Werkszustands-ERKENNUNG genutzt (ein lesender pwdgrp-Aufruf) und niemals
# gespeichert: laesst sich das Geraet damit anmelden, ist es noch werksseitig.
FACTORY_DEFAULT_USER = "root"
FACTORY_DEFAULT_PASSWORD = "pass"


def _default_login_works(ip, scheme, port, timeout) -> bool:
    """True, wenn der Werks-Standard-Login (root/pass) noch funktioniert.

    Aeltere AXIS-Firmware verlangt auch werksneu eine Authentifizierung, ist dann
    aber noch mit den Standard-Zugangsdaten erreichbar. Ein konfiguriertes Geraet
    weist sie mit 401 ab.
    """
    try:
        _request(ip, FACTORY_DEFAULT_USER, FACTORY_DEFAULT_PASSWORD,
                 "/axis-cgi/pwdgrp.cgi?action=get", scheme=scheme, port=port,
                 timeout=timeout, auth=True)
        return True
    except VapixError:
        return False


def is_unconfigured(ip, scheme="auto", port=None, timeout=10):
    """True, wenn sich das Geraet im Auslieferungszustand befindet (Ersteinrichtung
    noetig: noch kein individuelles Admin-Passwort gesetzt).

    Drei Faelle werden erkannt:
    - **Sehr alte Firmware:** ein unauthentifizierter VAPIX-Aufruf antwortet mit 200.
    - **AXIS OS 10/11:** ``pwdgrp.cgi`` antwortet mit 401, signalisiert den
      Werkszustand aber ueber den Header ``axis-setup`` bzw. den Body-Hinweis
      (siehe :func:`_is_setup_response`).
    - **Aeltere Firmware mit Standard-Login (z. B. M7001):** normaler 401, aber der
      Werks-Standard-Login ``root/pass`` funktioniert noch.

    Ein bereits konfiguriertes Geraet liefert einen normalen 401 und lehnt den
    Standard-Login ab -> False.
    """
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    path = "/axis-cgi/pwdgrp.cgi?action=get"
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{path}"
        opener = _build_opener(f"{ip}:{p}", "", "", auth=False)
        try:
            with opener.open(url, timeout=timeout) as resp:
                resp.read()
            return True  # 200 ohne Auth -> werksneu (sehr alte Firmware)
        except urllib.error.HTTPError as exc:
            if _is_setup_response(exc):
                return True   # AXIS OS: Ersteinrichtung noetig
            if exc.code == 401:
                # Normaler Auth-Challenge: koennte werksneu (Standard-Login aktiv)
                # oder konfiguriert sein -> per root/pass nachpruefen.
                return _default_login_works(ip, sc, p, timeout)
            continue  # anderer HTTP-Fehler: naechstes Schema versuchen
        except (urllib.error.URLError, TimeoutError, OSError):
            continue  # nicht erreichbar ueber dieses Schema
    return False


def is_online(ip, scheme="auto", port=None, timeout=5):
    """True, wenn das Geraet ueberhaupt per HTTP(S) antwortet (erreichbar).

    Im Gegensatz zu is_unconfigured zaehlt JEDE HTTP-Antwort als online -- auch
    401 (Auth verlangt) oder andere Fehlercodes bedeuten 'das Geraet ist da'. Nur
    Verbindungs-/Timeout-Fehler ueber alle Schemata hinweg gelten als offline.
    """
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    path = "/axis-cgi/pwdgrp.cgi?action=get"
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}{path}"
        opener = _build_opener(f"{ip}:{p}", "", "", auth=False)
        try:
            with opener.open(url, timeout=timeout) as resp:
                resp.read()
            return True                       # 200 -> online
        except urllib.error.HTTPError:
            return True                       # Geraet hat geantwortet (z. B. 401)
        except (urllib.error.URLError, TimeoutError, OSError):
            continue                          # ueber dieses Schema nicht erreichbar
    return False


def _parse_param_list(text):
    """Wandelt die 'root.Gruppe.Name=Wert'-Zeilen von param.cgi in ein Dict."""
    result = {}
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def _param_value(params, group):
    """Liest einen param.cgi-Wert unabhaengig vom 'root.'-Praefix: neuere Firmware
    liefert 'root.Gruppe.Name=...', aeltere (z. B. AXIS OS 5.x) nur 'Gruppe.Name=...'."""
    return params.get(f"root.{group}") or params.get(group) or ""


def _basic_device_info(ip, username, password, scheme="auto", port=None, timeout=10):
    """Liest Geraeteeigenschaften ueber basicdeviceinfo.cgi (JSON, AXIS OS).

    Liefert das ``propertyList``-Dict (u. a. ``Version``, ``ProdShortName``,
    ``ProdNbr``, ``SerialNumber``) oder ``{}``, wenn der Endpunkt nicht verfuegbar
    ist. Wirft VapixError nur bei fehlgeschlagener Authentifizierung (401), damit
    die aufrufende Zugangsdaten-Pruefung weiterhin funktioniert.
    """
    path = "/axis-cgi/basicdeviceinfo.cgi"
    body = json.dumps({"apiVersion": "1.0", "context": "kkm",
                       "method": "getAllProperties"}).encode("utf-8")
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        host_port = f"{ip}:{p}"
        url = f"{sc}://{host_port}{path}"
        opener = _build_opener(host_port, username, password)
        req = urllib.request.Request(url, data=body,
                                     headers={"Content-Type": "application/json"})
        try:
            with opener.open(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data.get("data", {}).get("propertyList", {}) or {}
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
            continue  # Endpunkt nicht vorhanden o. Ae. -> naechstes Schema
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            continue
    return {}


def get_device_info(ip, username, password, scheme="auto", port=None, timeout=10):
    """Liest Modell, Seriennummer und Firmware (lesender Test der Verbindung/Auth).

    Primaer ueber ``param.cgi`` (wirft bei 401 -> Zugangsdaten-Pruefung). Fehlt die
    Firmware dann noch (neuere AXIS OS liefern ueber param.cgi teils leere Werte
    oder eine ``# Error``-Antwort mit HTTP 200), wird ``basicdeviceinfo.cgi``
    ergaenzend abgefragt.
    """
    path = (
        "/axis-cgi/param.cgi?action=list"
        "&group=Brand.ProdShortName,Properties.System.SerialNumber,"
        "Properties.Firmware.Version"
    )
    params = _parse_param_list(
        _request_auto(ip, username, password, path, scheme, port, timeout)
    )
    info = {
        "model": _param_value(params, "Brand.ProdShortName") or "?",
        "serial": _param_value(params, "Properties.System.SerialNumber") or "?",
        "firmware": _param_value(params, "Properties.Firmware.Version"),
    }
    # Fallback fuer moderne Geraete: fehlende Firmware/Modell per JSON-Endpunkt.
    if not info["firmware"] or info["model"] in ("", "?"):
        props = _basic_device_info(ip, username, password, scheme, port, timeout)
        if props:
            if not info["firmware"]:
                info["firmware"] = props.get("Version", "") or ""
            if info["model"] in ("", "?"):
                info["model"] = (props.get("ProdShortName") or props.get("ProdNbr")
                                 or info["model"])
            if info["serial"] in ("", "?"):
                info["serial"] = props.get("SerialNumber", "") or info["serial"]
    # Fallback fuer aeltere Geraete (z. B. AXIS OS 5.x): manche Firmware liefert
    # auf eine kombinierte Gruppen-Abfrage gar nichts, beantwortet aber Einzel-
    # gruppen. Firmware/Modell daher einzeln nachfragen, falls noch leer.
    if not info["firmware"]:
        info["firmware"] = _single_param(
            ip, username, password, "Properties.Firmware.Version",
            scheme, port, timeout) or info["firmware"]
    if info["model"] in ("", "?"):
        info["model"] = _single_param(
            ip, username, password, "Brand.ProdShortName",
            scheme, port, timeout) or info["model"]
    return info


def _single_param(ip, username, password, group, scheme="auto", port=None, timeout=10):
    """Liest genau einen param.cgi-Parameter (Einzelgruppe, kompatibel mit alter
    Firmware). Liefert den Wert oder \"\" (schluckt Lesefehler bis auf 401)."""
    path = f"/axis-cgi/param.cgi?action=list&group={group}"
    try:
        params = _parse_param_list(
            _request_auto(ip, username, password, path, scheme, port, timeout))
    except VapixError:
        return ""
    return _param_value(params, group)


def _update_params(ip, username, password, params, scheme, port, timeout):
    """Ruft param.cgi?action=update mit den uebergebenen Parametern auf."""
    query = urllib.parse.urlencode(params)
    path = f"/axis-cgi/param.cgi?action=update&{query}"
    text = _request_auto(ip, username, password, path, scheme, port, timeout)
    # Erfolgreiche Updates antworten mit "OK"; Fehler beginnen mit "# Error".
    if "OK" not in text:
        raise VapixError(t("Geraet meldete: {body}", body=text.strip() or t("(leere Antwort)")))
    return text.strip()


def set_static_ip(ip, username, password, new_ip, subnet_mask, gateway,
                  scheme="auto", port=None, timeout=10):
    """Stellt die Kamera auf eine feste IP-Adresse um (BootProto=none)."""
    params = {
        "Network.BootProto": "none",
        "Network.IPAddress": new_ip,
        "Network.SubnetMask": subnet_mask,
    }
    if gateway:
        params["Network.DefaultRouter"] = gateway
    return _update_params(ip, username, password, params, scheme, port, timeout)


def set_dhcp(ip, username, password, scheme="auto", port=None, timeout=10):
    """Stellt die Kamera auf DHCP um (BootProto=dhcp)."""
    params = {"Network.BootProto": "dhcp"}
    return _update_params(ip, username, password, params, scheme, port, timeout)


def factory_default(ip, username, password, keep_ip=True,
                    scheme="auto", port=None, timeout=30):
    """Setzt die Kamera auf Werkseinstellungen zurueck. Das Geraet startet danach neu.

    - ``keep_ip=True``  -> ``factorydefault.cgi``: alle Parameter **ausser** den
      Netzwerkeinstellungen (IP, Maske, Gateway, BootProto) werden zurueckgesetzt.
    - ``keep_ip=False`` -> ``hardfactorydefault.cgi``: **alle** Parameter inkl.
      Netzwerk (die IP faellt auf den Auslieferungszustand/DHCP zurueck).

    Vorgehen: erst die Zugangsdaten pruefen (klare Fehlermeldung bei falschem
    Passwort), dann den Reset ausloesen. Beim Zuruecksetzen kappt das Geraet oft die
    Verbindung (Neustart) -> ein danach auftretender Verbindungsfehler ist KEIN
    Fehler und wird als Erfolg gewertet.
    """
    # 1) Auth vorab verifizieren (wirft VapixError bei 401).
    _request_auto(ip, username, password, "/axis-cgi/pwdgrp.cgi?action=get",
                  scheme, port, min(timeout, 10))
    # 2) Reset ausloesen.
    cgi = "factorydefault.cgi" if keep_ip else "hardfactorydefault.cgi"
    try:
        _request_auto(ip, username, password, f"/axis-cgi/{cgi}",
                      scheme, port, timeout)
    except VapixError:
        pass   # Reboot kappt die Verbindung -> erwartet, kein Fehler
    return t("auf Werkseinstellungen zurückgesetzt") + (
        t(" (IP erhalten)") if keep_ip else t(" (inkl. IP)"))


def next_ip(ip_str, step=1):
    """Liefert die um 'step' erhoehte IPv4-Adresse als String (fuer Start-IP-Modus)."""
    parts = [int(p) for p in ip_str.split(".")]
    if len(parts) != 4:
        raise ValueError(f"Ungueltige IPv4-Adresse: {ip_str}")
    value = (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]
    value += step
    return ".".join(str((value >> shift) & 0xFF) for shift in (24, 16, 8, 0))


# =====================================================================
# Benutzerverwaltung (regulaere Axis-Benutzer ueber pwdgrp.cgi)
# =====================================================================

# Rolle -> Axis-Sekundaergruppen (sgrp). "users" ist die Primaergruppe.
USER_ROLES = {
    "administrator": "admin:operator:viewer:ptz",
    "operator": "operator:viewer:ptz",
    "viewer": "viewer",
}

# Werks-/Standard-Zugangsdaten (Benutzer, Passwort), die im Auslieferungszustand
# durchprobiert werden. Aeltere Axis-Geraete (z. B. M7001) antworten auf root/pass.
DEFAULT_CREDENTIALS = [
    ("root", "pass"),
    ("root", "root"),
    ("root", "admin"),
    ("root", ""),
]


def add_user(ip, username, password, new_user, new_password, role="viewer",
             scheme="auto", port=None, timeout=10, authenticate=True):
    """Legt einen regulaeren Axis-Benutzer mit der gewuenschten Rolle an.

    Mit authenticate=False ohne Anmeldung (werksneue Kamera, Erstbenutzer).
    """
    # Der Benutzer "root" gehoert in die Primaergruppe "root" (Pflicht fuer den
    # Erstadmin werksneuer AXIS-OS-Geraete), alle anderen in "users".
    # Wichtig: KEIN comment-Parameter senden -- das laesst den Erstadmin auf
    # AXIS OS < 11.5 fehlschlagen ("not a valid initial admin user").
    params = {
        "action": "add",
        "user": new_user,
        "pwd": new_password,
        "grp": "root" if new_user == "root" else "users",
        "sgrp": USER_ROLES.get(role, "viewer"),
    }
    path = f"/axis-cgi/pwdgrp.cgi?{urllib.parse.urlencode(params)}"
    text = _request_auto(ip, username, password, path, scheme, port, timeout,
                         auth=authenticate)
    if "Error" in text:
        raise VapixError(t("Geraet meldete: {body}", body=text.strip()))
    return t("Benutzer '{user}' angelegt ({role})", user=new_user, role=role)


def set_user_password(ip, username, password, target_user, new_password,
                      scheme="auto", port=None, timeout=10, authenticate=True):
    """Aendert das Passwort eines bestehenden regulaeren Axis-Benutzers."""
    params = {"action": "update", "user": target_user, "pwd": new_password}
    path = f"/axis-cgi/pwdgrp.cgi?{urllib.parse.urlencode(params)}"
    text = _request_auto(ip, username, password, path, scheme, port, timeout,
                         auth=authenticate)
    if "Error" in text:
        raise VapixError(t("Geraet meldete: {body}", body=text.strip()))
    return t("Passwort von '{user}' geaendert", user=target_user)


def add_or_set_user(ip, username, password, new_user, new_password, role="viewer",
                    factory=False, scheme="auto", port=None, timeout=10):
    """Legt einen Benutzer an; mit factory=True wird der Auslieferungszustand
    behandelt: erst ohne Anmeldung, dann mit Standard-Zugangsdaten; existiert der
    Benutzer bereits, wird stattdessen dessen Passwort gesetzt (als Administrator).
    """
    if not factory:
        return add_user(ip, username, password, new_user, new_password, role,
                        scheme, port, timeout)
    attempts = [("", "", False)] + [(u, p, True) for u, p in DEFAULT_CREDENTIALS]
    last = None
    for usr, pwd, auth in attempts:
        try:
            try:
                return add_user(ip, usr, pwd, new_user, new_password,
                                "administrator", scheme, port, timeout, authenticate=auth)
            except VapixError:
                if not auth:
                    raise  # ohne Anmeldung kein Update-Fallback (moderne Geraete)
                return (set_user_password(ip, usr, pwd, new_user, new_password,
                                          scheme, port, timeout, authenticate=auth)
                        + t(" (vorhandener Benutzer, Passwort gesetzt)"))
        except VapixError as exc:
            # Lehnt das Geraet den *unauthentifizierten* Erstversuch mit einer echten
            # Antwort ab (HTTP 200 + Fehlertext, kein 401) — etwa die Passwort-Policy von
            # AXIS OS 13: „invalid password" —, ist DAS die maßgebliche Ursache. Nicht mit
            # den Werks-Zugangsdaten weiterprobieren: die liefern auf einem Setup-Geraet
            # ohnehin 401 und wuerden die eigentliche Meldung mit „Authentifizierung
            # fehlgeschlagen" verschleiern.
            if not auth and not getattr(exc, "auth_failed", False):
                raise
            last = exc
    raise last if last is not None else VapixError("kein Zugang moeglich")


# =====================================================================
# ONVIF-Benutzerverwaltung (ONVIF Device Service per SOAP)
# =====================================================================

ONVIF_LEVELS = ("Administrator", "Operator", "User")

# ONVIF-Benutzer werden ueber den VAPIX-SOAP-Endpoint /vapix/services verwaltet
# (HTTP-Digest mit VAPIX-Admin), NICHT ueber /onvif/device_service (das ONVIF-
# Auth/WS-Security verlangen wuerde). Genau so macht es der Axis Device Manager.
_ONVIF_ENVELOPE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soap:Envelope '
    'xmlns:tt="http://www.onvif.org/ver10/schema" '
    'xmlns:tds="http://www.onvif.org/ver10/device/wsdl" '
    'xmlns:soap="http://www.w3.org/2003/05/soap-envelope">'
    '<soap:Body>{body}</soap:Body></soap:Envelope>'
)


def _xml_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def _extract_soap_fault(text):
    """Holt eine lesbare Fehlermeldung aus einer SOAP-Fault-Antwort.

    Praefix-unabhaengig (z. B. <SOAP-ENV:Text>, <s:Text>, <faultstring>),
    SOAP 1.2 (Reason/Text) zuerst, dann SOAP 1.1 (faultstring).
    """
    for pat in (r"<(?:[\w-]+:)?Text[^>]*>([^<]+)</(?:[\w-]+:)?Text>",
                r"<(?:[\w-]+:)?faultstring[^>]*>([^<]+)</(?:[\w-]+:)?faultstring>"):
        m = re.search(pat, text)
        if m and m.group(1).strip():
            return m.group(1).strip()
    return ""


def _onvif_post(ip, username, password, inner, scheme, port, timeout):
    """POSTet einen SOAP-Body an den VAPIX-Services-Endpoint (HTTP-Digest-Auth)."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}/vapix/services"
    body = _ONVIF_ENVELOPE.format(body=inner).encode("utf-8")
    opener = _build_opener(host_port, username, password)
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "text/xml"})
    try:
        with opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        detail = exc.read().decode("utf-8", errors="replace")
        reason = _extract_soap_fault(detail) or f"HTTP {exc.code}: {exc.reason}"
        raise VapixError(t("ONVIF-Fehler: {reason}", reason=reason))
    except urllib.error.URLError as exc:
        raise VapixConnectError(t("Nicht erreichbar: {reason}", reason=exc.reason))
    except (TimeoutError, OSError) as exc:
        raise VapixConnectError(t("Verbindungsfehler: {err}", err=exc))


def _onvif_post_auto(ip, username, password, inner, scheme, port, timeout):
    """Wie _onvif_post, aber 'auto' probiert erst HTTPS, dann HTTP (Rueckfall nur
    bei Verbindungsfehlern, siehe VapixConnectError)."""
    if scheme != "auto":
        return _onvif_post(ip, username, password, inner, scheme, port, timeout)
    try:
        return _onvif_post(ip, username, password, inner, "https", port, timeout)
    except VapixConnectError:
        return _onvif_post(ip, username, password, inner, "http", port, timeout)


def _check_onvif_response(text):
    """Wirft VapixError, wenn die SOAP-Antwort einen Fault enthaelt."""
    if "Fault" in text:
        raise VapixError(t("ONVIF-Fehler: {reason}", reason=_extract_soap_fault(text) or text.strip()))


def add_onvif_user(ip, username, password, new_user, new_password,
                   level="Administrator", scheme="auto", port=None, timeout=10):
    """Legt einen ONVIF-Benutzer an (ONVIF CreateUsers ueber /vapix/services)."""
    inner = (
        '<tds:CreateUsers xmlns="http://www.onvif.org/ver10/device/wsdl"><User>'
        f"<tt:Username>{_xml_escape(new_user)}</tt:Username>"
        f"<tt:Password>{_xml_escape(new_password)}</tt:Password>"
        f"<tt:UserLevel>{level}</tt:UserLevel>"
        "</User></tds:CreateUsers>"
    )
    _check_onvif_response(
        _onvif_post_auto(ip, username, password, inner, scheme, port, timeout))
    return t("ONVIF-Benutzer '{user}' angelegt ({level})", user=new_user, level=level)


def set_onvif_user_password(ip, username, password, target_user, new_password,
                            level="Administrator", scheme="auto", port=None, timeout=10):
    """Aendert Passwort/Stufe eines ONVIF-Benutzers (ONVIF SetUser ueber /vapix/services)."""
    inner = (
        '<tds:SetUser xmlns="http://www.onvif.org/ver10/device/wsdl"><User>'
        f"<tt:Username>{_xml_escape(target_user)}</tt:Username>"
        f"<tt:Password>{_xml_escape(new_password)}</tt:Password>"
        f"<tt:UserLevel>{level}</tt:UserLevel>"
        "</User></tds:SetUser>"
    )
    _check_onvif_response(
        _onvif_post_auto(ip, username, password, inner, scheme, port, timeout))
    return t("ONVIF-Passwort von '{user}' geaendert", user=target_user)


def parse_user_list(path, onvif=False):
    """Liest eine Benutzerliste fuer den Stapel-Import aus einer Textdatei.

    Format: eine Zeile je Benutzer, kommagetrennt (CSV -- Passwoerter mit Komma
    in Anfuehrungszeichen setzen):

        Name,Passwort[,Rolle]

    Leerzeilen und mit '#' beginnende Zeilen werden uebersprungen. Fehlt die
    Rolle/Stufe, gilt der niedrigste Rang (regulaer 'viewer', ONVIF 'User').
    Gueltige Rollen (regulaer): administrator/operator/viewer; Stufen (ONVIF):
    Administrator/Operator/User -- Gross-/Kleinschreibung egal. Liefert eine
    Liste von Dicts {name, password, role}. Wirft VapixError bei Datei- oder
    Formatfehlern (mit Zeilennummern), damit nichts Halbfertiges angelegt wird.
    """
    try:
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
    except OSError as exc:
        raise VapixError(t("Datei nicht lesbar: {err}", err=exc))
    if onvif:
        valid = {lvl.lower(): lvl for lvl in ONVIF_LEVELS}
        default = "User"
    else:
        valid = {role: role for role in USER_ROLES}
        default = "viewer"
    users = []
    errors = []
    for num, row in enumerate(rows, 1):
        if not row:
            continue
        name = row[0].strip()
        if not name or name.startswith("#"):
            continue
        if len(row) < 2 or not row[1]:
            errors.append(t("Zeile {num}: Passwort fehlt", num=num))
            continue
        password = row[1]
        role_raw = row[2].strip() if len(row) >= 3 else ""
        if role_raw:
            role = valid.get(role_raw.lower())
            if role is None:
                errors.append(t("Zeile {num}: ungueltige Rolle/Stufe '{role}'", num=num, role=role_raw))
                continue
        else:
            role = default
        users.append({"name": name, "password": password, "role": role})
    if errors:
        raise VapixError("; ".join(errors))
    if not users:
        raise VapixError(t("Keine Benutzer in der Datei gefunden."))
    return users


# =====================================================================
# Firmware-Update
# =====================================================================

def _multipart_body(parts):
    """Baut einen multipart/form-data-Body.

    parts: Liste von (name, filename|None, content_type|None, data:bytes|str).
    Liefert (body_bytes, boundary).
    """
    boundary = "----AxisIPUtil" + os.urandom(12).hex()
    bb = boundary.encode("ascii")
    crlf = b"\r\n"
    buf = []
    for name, filename, ctype, data in parts:
        disp = f'form-data; name="{name}"'
        if filename is not None:
            disp += f'; filename="{filename}"'
        buf.append(b"--" + bb)
        buf.append(b"Content-Disposition: " + disp.encode("utf-8"))
        if ctype:
            buf.append(b"Content-Type: " + ctype.encode("ascii"))
        buf.append(b"")
        buf.append(data if isinstance(data, bytes) else data.encode("utf-8"))
    buf.append(b"--" + bb + b"--")
    buf.append(b"")
    return crlf.join(buf), boundary


def _post_multipart(ip, username, password, path, parts, scheme, port, timeout):
    """POSTet einen multipart/form-data-Body und liefert den Antworttext."""
    if port is None:
        port = DEFAULT_PORTS[scheme]
    host_port = f"{ip}:{port}"
    url = f"{scheme}://{host_port}{path}"
    body, boundary = _multipart_body(parts)
    opener = _build_opener(host_port, username, password)
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with opener.open(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _parse_fw_response(resp):
    """Wertet die JSON-Antwort von firmwaremanagement.cgi aus."""
    try:
        obj = json.loads(resp)
    except ValueError:
        # kein JSON -> grobe Heuristik
        if re.search(r"error|fail", resp, re.IGNORECASE):
            raise VapixError(t("Geraet meldete: {body}", body=resp.strip()[:200]))
        return t("Firmware-Upgrade gestartet")
    if isinstance(obj, dict) and obj.get("error"):
        err = obj["error"]
        raise VapixError(t("Fehler {code}: {message}", code=err.get('code', '?'), message=err.get('message', err)))
    version = ""
    if isinstance(obj, dict):
        version = obj.get("data", {}).get("firmwareVersion", "")
    return t("Firmware aktualisiert") + (t(" auf {version}", version=version) if version else "")


def _resolve_scheme(ip, username, password, scheme, port, timeout):
    """Ermittelt ein Schema (https/http), ueber das die Kamera erreichbar ist."""
    schemes = ["https", "http"] if scheme == "auto" else [scheme]
    for sc in schemes:
        p = port if port else DEFAULT_PORTS[sc]
        url = f"{sc}://{ip}:{p}/axis-cgi/param.cgi?action=list&group=Properties.Firmware.Version"
        opener = _build_opener(f"{ip}:{p}", username, password)
        try:
            with opener.open(url, timeout=timeout) as r:
                r.read()
            return sc
        except urllib.error.HTTPError:
            return sc  # verbunden (z. B. 401) -> Schema funktioniert
        except (urllib.error.URLError, TimeoutError, OSError):
            continue
    return None


def _has_firmware_api(ip, username, password, scheme, port, timeout):
    """Prueft mit einem kleinen JSON-Aufruf, ob firmwaremanagement.cgi existiert."""
    p = port if port else DEFAULT_PORTS[scheme]
    url = f"{scheme}://{ip}:{p}/axis-cgi/firmwaremanagement.cgi"
    body = json.dumps({"apiVersion": "1.0", "context": "probe", "method": "status"})
    opener = _build_opener(f"{ip}:{p}", username, password)
    req = urllib.request.Request(url, data=body.encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    try:
        with opener.open(req, timeout=timeout) as r:
            r.read()
        return True
    except urllib.error.HTTPError as exc:
        return exc.code not in (404, 501)  # existiert, nur z. B. 401/400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False  # CGI fehlt / Verbindung zurueckgesetzt -> Legacy


def _modern_upgrade(ip, username, password, filename, data, factory_default,
                    scheme, port, timeout):
    payload = json.dumps({
        "apiVersion": "1.0", "context": "axisiputil", "method": "upgrade",
        "params": {"factoryDefaultMode": "hard" if factory_default else "none"},
    })
    parts = [("payload", None, None, payload),
             ("file", filename, "application/octet-stream", data)]
    try:
        resp = _post_multipart(ip, username, password,
                               "/axis-cgi/firmwaremanagement.cgi",
                               parts, scheme, port, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        raise VapixError(t("HTTP-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
    except (urllib.error.URLError, TimeoutError, OSError):
        return t("Firmware hochgeladen - Geraet startet neu (bitte Status pruefen)")
    return _parse_fw_response(resp)


def _legacy_upgrade(ip, username, password, filename, data, scheme, port, timeout):
    """Aelterer Upgrade-Weg (firmwareupgrade.cgi) fuer Geraete ohne die JSON-API.

    Aeltere Geraete trennen die Verbindung, sobald sie mit dem Flashen beginnen
    -- das wird daher als Erfolg (Neustart laeuft) gewertet.
    """
    parts = [("file", filename, "application/octet-stream", data)]
    try:
        resp = _post_multipart(ip, username, password, "/axis-cgi/firmwareupgrade.cgi",
                               parts, scheme, port, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise _auth_error(t("Authentifizierung fehlgeschlagen (Benutzer/Passwort?)."))
        raise VapixError(t("HTTP-Fehler {code}: {reason}", code=exc.code, reason=exc.reason))
    except (urllib.error.URLError, TimeoutError, OSError):
        return t("Firmware hochgeladen (Legacy) - Verbindung getrennt, Geraet flasht/startet neu (bitte pruefen)")
    if re.search(r"error|fail", resp, re.IGNORECASE):
        raise VapixError(t("Geraet meldete: {body}", body=resp.strip()[:200]))
    return t("Firmware hochgeladen (Legacy) - Geraet startet neu")


def upgrade_firmware(ip, username, password, firmware_path, scheme="auto",
                     port=None, timeout=600, factory_default=False):
    """Spielt eine Firmware-Datei auf die Kamera auf.

    Ermittelt zuerst per kleinem Probe-Request, ob die moderne JSON-API
    (firmwaremanagement.cgi) vorhanden ist; sonst Legacy (firmwareupgrade.cgi),
    damit die grosse Datei nicht an einen nicht vorhandenen Endpoint geht. Das
    Geraet startet nach dem Upgrade selbsttaetig neu.
    """
    with open(firmware_path, "rb") as f:
        data = f.read()
    filename = os.path.basename(firmware_path)

    sc = _resolve_scheme(ip, username, password, scheme, port, timeout=15)
    if sc is None:
        raise VapixError(t("Kamera nicht erreichbar."))
    if _has_firmware_api(ip, username, password, sc, port, timeout=15):
        return _modern_upgrade(ip, username, password, filename, data,
                               factory_default, sc, port, timeout)
    return _legacy_upgrade(ip, username, password, filename, data, sc, port, timeout)


# =====================================================================
# Axis-Device-Manager-Konfigurationsdateien (.cfg / AcmDeviceParameterExport)
# =====================================================================

def parse_adm_config(path):
    """Liest eine ADM-.cfg (XML) und liefert Modell, Firmware, Parameter, Profile.

    Wirft VapixError bei ungueltigem Format.
    """
    try:
        with open(path, "rb") as f:
            root = ET.fromstring(f.read())
    except (OSError, ET.ParseError) as exc:
        raise VapixError(t("Datei nicht lesbar/kein gueltiges XML: {err}", err=exc))
    if root.tag != "AcmDeviceParameterExport":
        raise VapixError(t("Keine ADM-Konfigurationsdatei (AcmDeviceParameterExport)."))

    params = {}
    for p in root.findall("./ParameterList/Parameter"):
        name = (p.findtext("Name") or "").strip()
        if name:
            params[name] = p.findtext("Value") or ""
    profiles = []
    for sp in root.findall("./StreamProfileList/StreamProfile"):
        name = (sp.findtext("Name") or "").strip()
        if name:
            profiles.append({
                "name": name,
                "description": sp.findtext("Description") or "",
                "parameters": sp.findtext("Parameters") or "",
            })
    # Bewegungserkennung (VMD4): ADM legt die Konfiguration als JSON-Blob unter
    # <Vmd4><Vmd4Configuration> ab (kein param.cgi -> eigene Steuer-API).
    vmd4 = None
    vmd4_text = (root.findtext("./Vmd4/Vmd4Configuration") or "").strip()
    if vmd4_text:
        try:
            vmd4 = json.loads(vmd4_text)
        except ValueError as exc:
            raise VapixError(t("Vmd4-Konfiguration ist kein gueltiges JSON: {err}", err=exc))
    return {
        "model": root.findtext("Model") or "",
        "firmware": root.findtext("FirmwareVersion") or "",
        "parameters": params,
        "profiles": profiles,
        "vmd4": vmd4,
    }


# Schreibgeschuetzte VAPIX-Parametergruppen: param.cgi?action=update akzeptiert sie
# nicht. AXIS-Device-Manager-Exporte schreiben sie dennoch mit (dumpen alles) --
# wird die Gruppe mitgesendet, lehnt die Kamera den GESAMTEN Update-Batch ab
# (AXIS OS 12: HTTP 401 "Basic realm=..."). Daher vor dem Anwenden herausfiltern.
READONLY_PARAM_PREFIXES = ("Properties.",)


def _writable_params(params):
    """Entfernt schreibgeschuetzte (Properties.*) Parameter aus einem Param-Dict."""
    return {k: v for k, v in params.items()
            if not k.startswith(READONLY_PARAM_PREFIXES)}


def _param_batch_ok(text) -> bool:
    """True, wenn eine ``param.cgi?action=update``-Antwort keinen Fehler meldet."""
    return not re.search(r"#\s*Error|^Error", text, re.IGNORECASE | re.MULTILINE)


def _auth_ok(ip, username, password, scheme, port, timeout) -> bool:
    """True, wenn ein *lesender* ``param.cgi``-Aufruf mit den Zugangsdaten durchgeht.

    Dient dazu, ein 401 auf einen ``update`` einzuordnen: liegt es am **falschen
    Passwort** (dann schlaegt auch dieser Lese-Aufruf mit 401 fehl) oder daran, dass
    das Geraet einen **Parameter nicht erlaubt** (Lesen geht, Schreiben nicht)?
    """
    try:
        _request_auto(ip, username, password,
                      "/axis-cgi/param.cgi?action=list&group=Brand.Brand",
                      scheme, port, timeout)
        return True
    except VapixError:
        return False


def _try_one_param(ip, username, password, name, value, scheme, port, timeout) -> bool:
    """Setzt genau **einen** param.cgi-Parameter; True bei Erfolg, False, wenn das
    Geraet ihn ablehnt (``# Error``-Antwort). Auth-/Verbindungsfehler propagieren."""
    text = _post_form_auto(ip, username, password, "/axis-cgi/param.cgi",
                           {"action": "update", name: value}, scheme, port, timeout)
    return _param_batch_ok(text)


def apply_parameters(ip, username, password, params, scheme="auto", port=None, timeout=30):
    """Setzt eine Reihe von param.cgi-Parametern und liefert ``(angewendet, abgelehnt)``.

    Zuerst ein einziger Batch-``update``. Lehnt das Geraet ihn ab (etwa weil eine
    Quell-``.cfg`` einen in dieser Firmware **entfernten/obsoleten** Parameter enthaelt —
    in neueren AXIS OS zunehmend, siehe AXIS OS 13), wird **parameterweise** nachgefahren:
    die gueltigen werden angewendet, die vom Geraet abgelehnten in ``abgelehnt``
    (Parameternamen) gesammelt statt den ganzen Import scheitern zu lassen.

    Schreibgeschuetzte ``Properties.*``-Parameter werden vorab ignoriert (sonst weist die
    Kamera den kompletten Batch ab). Ein 401 auf den Batch wird erst als Auth-Problem
    weitergereicht (→ erneute Passwortabfrage), wenn ein Lesezugriff bestaetigt, dass die
    Zugangsdaten wirklich nicht mehr stimmen — sonst gilt es als Parameter-Ablehnung
    (kein N-faches Einzel-Login, das die Brute-Force-Sperre des Geraets ausloesen wuerde).
    """
    params = _writable_params(params)
    if not params:
        return 0, []
    fields = {"action": "update"}
    fields.update(params)
    try:
        text = _post_form_auto(ip, username, password, "/axis-cgi/param.cgi",
                               fields, scheme, port, timeout)
        if _param_batch_ok(text):
            return len(params), []
    except VapixConnectError:
        raise
    except VapixError as exc:
        if getattr(exc, "auth_failed", False) and not _auth_ok(
                ip, username, password, scheme, port, timeout):
            raise   # wirklich falsches Passwort -> Re-Auth im Aktionsdialog

    # Batch abgelehnt -> einzeln, um die guten anzuwenden und die schlechten zu isolieren.
    applied, rejected = 0, []
    for name, value in params.items():
        try:
            if _try_one_param(ip, username, password, name, value, scheme, port, timeout):
                applied += 1
            else:
                rejected.append(name)
        except VapixConnectError:
            raise
        except VapixError:
            rejected.append(name)   # Auth ist gepreuft ok -> Ablehnung des Parameters
    return applied, rejected


def _existing_stream_profiles(ip, username, password, scheme, port, timeout):
    """Liefert {Profilname: 'S#'} der vorhandenen Stream-Profile (param.cgi).

    Funktioniert sowohl bei modernen als auch aelteren Geraeten -- beide pflegen
    die Profile im param.cgi-Baum 'StreamProfile.S#'.
    """
    text = _request_auto(ip, username, password,
                         "/axis-cgi/param.cgi?action=list&group=StreamProfile",
                         scheme, port, timeout)
    mapping = {}
    for line in text.splitlines():
        m = re.match(r"root\.StreamProfile\.(S\d+)\.Name=(.+)$", line.strip())
        if m:
            mapping[m.group(2).strip()] = m.group(1)
    return mapping


def _sp_update(ip, username, password, sid, profile, scheme, port, timeout):
    """Ueberschreibt ein vorhandenes Profil StreamProfile.<sid> in place."""
    fields = {
        "action": "update",
        f"StreamProfile.{sid}.Name": profile["name"],
        f"StreamProfile.{sid}.Description": profile["description"],
        f"StreamProfile.{sid}.Parameters": profile["parameters"],
    }
    text = _post_form(ip, username, password, "/axis-cgi/param.cgi",
                      fields, scheme, port, timeout)
    if re.search(r"#\s*Error|failed", text, re.IGNORECASE):
        raise VapixError(t("Profil '{name}': {body}", name=profile['name'], body=text.strip()[:120]))


def _sp_add(ip, username, password, profile, scheme, port, timeout):
    """Legt ein neues Stream-Profil per param.cgi an (modern wie legacy)."""
    fields = {
        "action": "add",
        "template": "streamprofile",
        "group": "StreamProfile",
        "StreamProfile.S.Name": profile["name"],
        "StreamProfile.S.Description": profile["description"],
        "StreamProfile.S.Parameters": profile["parameters"],
    }
    text = _post_form(ip, username, password, "/axis-cgi/param.cgi",
                      fields, scheme, port, timeout)
    if re.search(r"#\s*Error|failed", text, re.IGNORECASE):
        raise VapixError(t("Profil '{name}': {body}", name=profile['name'], body=text.strip()[:120]))


def apply_stream_profiles(ip, username, password, profiles, scheme, port, timeout):
    """Wendet Stream-Profile an: vorhandene (gleicher Name) werden ueberschrieben,
    neue angelegt. Einheitlich ueber param.cgi. Liefert
    (angelegt, ueberschrieben, fehlgeschlagen).
    """
    if not profiles:
        return (0, 0, 0)
    existing = _existing_stream_profiles(ip, username, password, scheme, port, timeout)
    created = updated = failed = 0
    for prof in profiles:
        try:
            sid = existing.get(prof["name"])
            if sid:
                _sp_update(ip, username, password, sid, prof, scheme, port, timeout)
                updated += 1
            else:
                _sp_add(ip, username, password, prof, scheme, port, timeout)
                created += 1
        except VapixError:
            failed += 1
    return (created, updated, failed)


# VMD4 (Video Motion Detection 4) — die ACAP-Anwendung hat eine eigene JSON-
# Steuer-API (nicht param.cgi). ADM exportiert/importiert die Konfiguration darueber.
VMD4_CONTROL_PATH = "/local/vmd/control.cgi"
VMD4_API_VERSION = "1.4"
VMD4_PACKAGE = "vmd"


def _app_control(ip, username, password, action, package, scheme, port, timeout):
    """Startet/stoppt eine ACAP-Anwendung ueber applications/control.cgi.

    Liefert den (Klartext-)Antworttext. Wirft VapixError bei HTTP-/Netzwerkfehler.
    """
    path = f"/axis-cgi/applications/control.cgi?action={action}&package={package}"
    return _request_auto(ip, username, password, path, scheme, port, timeout)


def _vmd4_ping(ip, username, password, scheme, port, timeout):
    """True, wenn die VMD4-Steuer-API antwortet (App laeuft). Ein gestopptes ACAP
    liefert an seinem control.cgi einen generischen HTTP 500."""
    try:
        data = _post_json_auto(
            ip, username, password, VMD4_CONTROL_PATH,
            {"apiVersion": VMD4_API_VERSION, "method": "getSupportedVersions"},
            scheme, port, timeout)
        return isinstance(data, dict) and (
            "data" in data or "apiVersion" in data or "error" in data)
    except VapixError:
        return False


def _ensure_vmd_running(ip, username, password, scheme, port, timeout):
    """Stellt sicher, dass die VMD-Anwendung laeuft — sonst antwortet ihr
    control.cgi mit HTTP 500. Startet sie bei Bedarf und wartet, bis die Steuer-API
    erreichbar ist. Wirft VapixError, wenn das nicht gelingt.
    """
    if _vmd4_ping(ip, username, password, scheme, port, timeout):
        return
    try:
        _app_control(ip, username, password, "start", VMD4_PACKAGE, scheme, port, timeout)
    except VapixError as exc:
        raise VapixError(t(
            "VMD4-Anwendung ist nicht aktiv und liess sich nicht starten "
            "({err}). Ist 'AXIS Video Motion Detection' auf der Kamera installiert?", err=exc))
    for _ in range(8):                     # App braucht nach dem Start einen Moment
        time.sleep(1)
        if _vmd4_ping(ip, username, password, scheme, port, timeout):
            return
    raise VapixError(t("VMD4-Anwendung wurde gestartet, antwortet aber nicht "
                     "rechtzeitig — bitte erneut versuchen."))


def _vmd4_api_version(ip, username, password, scheme, port, timeout):
    """Ermittelt die hoechste von der Kamera unterstuetzte VMD4-API-Version.

    Verschiedene Firmware unterstuetzt verschiedene Versionen. Faellt bei nicht
    verfuegbarer Auskunft auf ``VMD4_API_VERSION`` zurueck. (getSupportedVersions
    selbst verlangt ein ``apiVersion``-Feld, sonst Fehler 2003.)
    """
    try:
        data = _post_json_auto(
            ip, username, password, VMD4_CONTROL_PATH,
            {"apiVersion": "1.0", "method": "getSupportedVersions"},
            scheme, port, timeout)
        versions = (data.get("data") or {}).get("apiVersions") or []
    except VapixError:
        versions = []
    valid = [v for v in versions if isinstance(v, str)
             and all(p.isdigit() for p in v.split("."))]
    if valid:
        return max(valid, key=lambda v: tuple(int(p) for p in v.split(".")))
    return VMD4_API_VERSION


def apply_vmd4_config(ip, username, password, vmd4, scheme="auto", port=None, timeout=30):
    """Wendet eine VMD4-(Bewegungserkennung)-Konfiguration an.

    'vmd4' ist das geparste Konfigurationsobjekt (parse_adm_config()['vmd4'] —
    cameras/profiles/…). Startet bei Bedarf zuerst die VMD-Anwendung und nutzt dann
    die JSON-Steuer-API (POST /local/vmd/control.cgi, method 'setConfiguration').
    Wirft VapixError, wenn die Anwendung fehlt/nicht startet oder die Konfiguration
    abgelehnt wird.
    """
    _ensure_vmd_running(ip, username, password, scheme, port, timeout)
    api_version = _vmd4_api_version(ip, username, password, scheme, port, timeout)
    body = {"apiVersion": api_version, "context": "kkm",
            "method": "setConfiguration", "params": vmd4}
    data = _post_json_auto(ip, username, password, VMD4_CONTROL_PATH, body,
                           scheme, port, timeout)
    err = data.get("error") if isinstance(data, dict) else None
    if err:
        detail = err.get("message") if isinstance(err, dict) else err
        raise VapixError(t("VMD4 lehnte die Konfiguration ab: {detail}", detail=detail))
    return True


def apply_adm_config(ip, username, password, config, scheme="auto", port=None,
                     timeout=30, with_profiles=True, selected_params=None,
                     selected_profiles=None, with_vmd4=True):
    """Wendet eine geparste ADM-Konfiguration an (Parameter, optional Profile,
    optional Bewegungserkennung/VMD4).

    'config' ist das Dict aus parse_adm_config(). Die Auswahl-Argumente spiegeln
    write_adm_config(), damit sich beim Import genauso filtern laesst wie beim
    Export: 'selected_params' (Menge von Namen; None = alle), 'selected_profiles'
    (Menge von Profilnamen; None = alle), 'with_vmd4' fuer die Bewegungserkennung.

    Liefert eine Ergebnis-Meldung. Schlaegt die VMD4-Uebernahme fehl, wird
    VapixError geworfen (die Meldung nennt zusaetzlich, was zuvor bereits
    erfolgreich angewendet wurde).
    """
    sc = _resolve_scheme(ip, username, password, scheme, port, timeout=15) or scheme
    params = {name: value for name, value in config.get("parameters", {}).items()
              if selected_params is None or name in selected_params}
    count, rejected = apply_parameters(ip, username, password, params, sc, port, timeout)
    msg = t("{count} Parameter angewendet", count=count)
    if rejected:
        shown = ", ".join(rejected[:8]) + ("…" if len(rejected) > 8 else "")
        msg += t("; {n} vom Gerät abgelehnt/übersprungen: {names}",
                 n=len(rejected), names=shown)
    profiles = [p for p in config.get("profiles", [])
                if selected_profiles is None or p.get("name") in selected_profiles]
    if with_profiles and profiles:
        created, updated, failed = apply_stream_profiles(
            ip, username, password, profiles, sc, port, timeout)
        msg += t("; Profile: {created} angelegt, {updated} ueberschrieben, {failed} fehlgeschlagen",
                 created=created, updated=updated, failed=failed)
    if with_vmd4 and config.get("vmd4") is not None:
        try:
            apply_vmd4_config(ip, username, password, config["vmd4"], sc, port, timeout)
            msg += t("; Bewegungserkennung (VMD4) angewendet")
        except VapixError as exc:
            raise VapixError(t("{msg}; Bewegungserkennung (VMD4) fehlgeschlagen: {err}", msg=msg, err=exc))
    return msg


# ---------------------------------------------------------------------
# Konfiguration AUSLESEN und als ADM-.cfg speichern (Umkehrung von oben)
# ---------------------------------------------------------------------

def _stream_profiles_from_params(full_params):
    """Baut die Stream-Profil-Liste aus dem vollstaendigen param.cgi-Baum.

    'full_params' ist {root.Gruppe.Name: Wert}. Liefert je StreamProfile.S#
    ein Dict {name, description, parameters} -- gleiches Format wie
    parse_adm_config()['profiles'].
    """
    sids = {}
    for key, value in full_params.items():
        m = re.match(r"root\.StreamProfile\.(S\d+)\.(Name|Description|Parameters)$", key)
        if m:
            sids.setdefault(m.group(1), {})[m.group(2)] = value
    profiles = []
    for sid in sorted(sids):
        d = sids[sid]
        name = (d.get("Name") or "").strip()
        if name:
            profiles.append({
                "name": name,
                "description": d.get("Description", ""),
                "parameters": d.get("Parameters", ""),
            })
    return profiles


def read_vmd4_config(ip, username, password, scheme="auto", port=None, timeout=30):
    """Liest die aktuelle VMD4-(Bewegungserkennung)-Konfiguration (getConfiguration).

    Liefert das Konfigurationsobjekt (cameras/profiles/…) oder ``None``, wenn die
    VMD-Anwendung nicht vorhanden/aktiv ist. **Ohne Seiteneffekt** — anders als der
    Import wird die App hier nicht gestartet (ein gestopptes ACAP liefert 500, das
    wird als „nicht verfuegbar" behandelt).
    """
    try:
        api_version = _vmd4_api_version(ip, username, password, scheme, port, timeout)
        data = _post_json_auto(
            ip, username, password, VMD4_CONTROL_PATH,
            {"apiVersion": api_version, "context": "kkm", "method": "getConfiguration"},
            scheme, port, timeout)
    except VapixError:
        return None
    if not isinstance(data, dict) or data.get("error"):
        return None
    cfg = data.get("data")
    return cfg if isinstance(cfg, dict) else None


def read_device_config(ip, username, password, scheme="auto", port=None, timeout=30):
    """Liest die komplette Geraetekonfiguration (param.cgi?action=list + VMD4).

    Liefert ein Dict im selben Format wie parse_adm_config() (model, firmware,
    parameters, profiles, vmd4). Die Parameternamen sind ohne 'root.'-Praefix
    gespeichert -- genau so, wie param.cgi?action=update sie erwartet und die
    .cfg-Datei sie ablegt, sodass write_adm_config()/parse_adm_config()/
    apply_adm_config() einen sauberen Round-Trip ergeben. ``vmd4`` ist ``None``,
    wenn keine (aktive) VMD-Anwendung vorhanden ist.
    """
    text = _request_auto(ip, username, password,
                         "/axis-cgi/param.cgi?action=list", scheme, port, timeout)
    full = _parse_param_list(text)
    if not full:
        raise VapixError("Keine Parameter erhalten (leere Antwort von param.cgi).")
    params = {}
    for key, value in full.items():
        # Neuere Firmware liefert 'root.'-Praefix, aeltere (AXIS OS 5.x) nicht.
        params[key[len("root."):] if key.startswith("root.") else key] = value
    return {
        "model": _param_value(full, "Brand.ProdShortName"),
        "firmware": _param_value(full, "Properties.Firmware.Version"),
        "parameters": params,
        "profiles": _stream_profiles_from_params(full),
        "vmd4": read_vmd4_config(ip, username, password, scheme, port, timeout),
    }


def write_adm_config(path, config, selected_params=None, with_profiles=True,
                     with_vmd4=True, selected_profiles=None):
    """Schreibt eine ADM-.cfg (AcmDeviceParameterExport) aus einer Konfiguration.

    'config' ist das Dict aus read_device_config()/parse_adm_config(). Ist
    'selected_params' (eine Menge von Namen) gesetzt, werden nur diese
    Parameter exportiert, sonst alle. 'with_profiles' steuert die Stream-Profile
    (und 'selected_profiles' -- eine Menge von Profilnamen -- welche davon; None =
    alle), 'with_vmd4' die Bewegungserkennung (nur geschrieben, wenn
    ``config['vmd4']`` vorhanden ist). Liefert die Anzahl geschriebener Parameter.
    """
    params = config.get("parameters", {})
    names = [n for n in sorted(params)
             if selected_params is None or n in selected_params]
    root = ET.Element("AcmDeviceParameterExport")
    ET.SubElement(root, "Model").text = config.get("model", "") or ""
    ET.SubElement(root, "FirmwareVersion").text = config.get("firmware", "") or ""
    plist = ET.SubElement(root, "ParameterList")
    for name in names:
        p = ET.SubElement(plist, "Parameter")
        ET.SubElement(p, "Name").text = name
        ET.SubElement(p, "Value").text = params[name]
    splist = ET.SubElement(root, "StreamProfileList")
    if with_profiles:
        for prof in config.get("profiles", []):
            if selected_profiles is not None and prof.get("name") not in selected_profiles:
                continue
            sp = ET.SubElement(splist, "StreamProfile")
            ET.SubElement(sp, "Name").text = prof.get("name", "")
            ET.SubElement(sp, "Description").text = prof.get("description", "")
            ET.SubElement(sp, "Parameters").text = prof.get("parameters", "")
    # Bewegungserkennung (VMD4) als eigener Block, kompaktes JSON wie im ADM-Export.
    if with_vmd4 and config.get("vmd4") is not None:
        ET.SubElement(root, "Vmd2")
        vmd4 = ET.SubElement(root, "Vmd4")
        ET.SubElement(vmd4, "Vmd4Configuration").text = json.dumps(
            config["vmd4"], separators=(",", ":"))
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    try:
        tree.write(path, encoding="utf-8", xml_declaration=True)
    except OSError as exc:
        raise VapixError(t("Datei nicht schreibbar: {err}", err=exc))
    return len(names)


# --- Geraete-Sicherung (Device Configuration API, AXIS OS 11.8+) -------------
# Die DCA sichert/spielt die *vollstaendige* Geraetekonfiguration als ein Objekt.
# Anders als die ADM-Parametervorlage (parse/write/apply_adm_config, Capability
# CONFIG) ist das ein geraetespezifisches Komplett-Abbild (IP, Name, Ereignis-
# regeln, Zeit, Benutzer ...) — der Gegenpart zu Hikvision/Hanwha/Dahua-Backups
# (Capability CONFIG_BACKUP).
#
#   Export:  GET   /config/rest/$export  -> {"status":"success","data":{...}}
#   Import:  PATCH /config/rest/$import   <- {"data":{...},"options":{...}}
#
# Die gespeicherte Datei enthaelt den reinen ``data``-Teil (versionierte Ressourcen
# wie ``param.v2``, ``user-management.v2``, ``time.v2`` ...) — genau das Format, das
# die Weboberflaeche herunterlaedt. Passwoerter sind im Export nicht enthalten (AXIS
# laesst als Secret markierte Werte weg).

DEVICE_SETTINGS_EXPORT_PATH = "/config/rest/$export"
DEVICE_SETTINGS_IMPORT_PATH = "/config/rest/$import"
IMPORT_TYPES = ("merge", "default")


def _dca_error(obj):
    """Formuliert eine lesbare Meldung aus einer DCA-Fehlerantwort."""
    err = obj.get("error") if isinstance(obj, dict) else None
    if isinstance(err, dict):
        msg = err.get("message") or err.get("code")
        if msg:
            return t("Geraet meldete Fehler: {msg}", msg=msg)
    return t("Geraet meldete einen Fehler bei der Geraete-Sicherung.")


def _unwrap_backup(obj):
    """Liefert den reinen ``data``-Teil eines Sicherungsobjekts.

    Akzeptiert die volle ``$export``-Antwort ``{"status":..,"data":{...}}``, ein
    ``{"data":{...}}`` sowie die von der Weboberflaeche gespeicherte reine
    Ressourcen-Map (Top-Level-Schluessel wie ``param.v2``).
    """
    if not isinstance(obj, dict):
        raise VapixError(t("Sicherung ist kein JSON-Objekt."))
    data = obj.get("data")
    # Vollstaendige $export-Antwort oder {"data":...}: den data-Teil herausziehen.
    # (Eine reine Ressourcen-Map hat nie einen Schluessel "data".)
    if isinstance(data, dict) and ("status" in obj or set(obj) == {"data"}):
        return data
    return obj


def export_device_settings(ip, username, password, scheme="auto", port=None, timeout=60):
    """Liest die komplette Geraetekonfiguration (DCA ``$export``).

    Liefert den ``data``-Teil (Ressourcen-Map), fertig zum Speichern in eine
    ``.json``-Sicherungsdatei. Wirft VapixError, wenn das Geraet die DCA nicht
    unterstuetzt (aeltere Firmware als AXIS OS 11.8 -> HTTP 404).
    """
    try:
        text = _request_auto(ip, username, password, DEVICE_SETTINGS_EXPORT_PATH,
                             scheme, port, timeout)
    except VapixError as exc:
        if "404" in str(exc):
            raise VapixError(t("Geraet unterstuetzt keine Geraete-Sicherung "
                               "(benoetigt AXIS OS 11.8 oder neuer)."))
        raise
    try:
        obj = json.loads(text)
    except ValueError:
        raise VapixError(t("Unerwartete Antwort: {body}", body=text.strip()[:200]))
    if not isinstance(obj, dict):
        raise VapixError(t("Unerwartetes Sicherungsformat."))
    if obj.get("status") == "error":
        raise VapixError(_dca_error(obj))
    data = obj.get("data")
    if not isinstance(data, dict) or not data:
        raise VapixError(t("Sicherung enthielt keine Daten."))
    return data


def save_device_settings(ip, username, password, path, scheme="auto", port=None,
                         timeout=60):
    """Liest die Geraetekonfiguration und schreibt sie als JSON-Datei.

    Liefert die Anzahl gesicherter Ressourcen (Top-Level-Schluessel).
    """
    data = export_device_settings(ip, username, password, scheme, port, timeout)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
    except OSError as exc:
        raise VapixError(t("Datei nicht schreibbar: {err}", err=exc))
    return len(data)


def load_device_settings_backup(path):
    """Liest eine ``.json``-Sicherungsdatei und liefert die Ressourcen-Map.

    Toleriert sowohl das von der Weboberflaeche gespeicherte reine Format als auch
    eine vollstaendige ``$export``-Antwort mit ``status``/``data``-Huelle.
    """
    try:
        with open(path, "r", encoding="utf-8") as fh:
            obj = json.load(fh)
    except OSError as exc:
        raise VapixError(t("Datei nicht lesbar: {err}", err=exc))
    except ValueError as exc:
        raise VapixError(t("Keine gueltige JSON-Sicherung: {err}", err=exc))
    data = _unwrap_backup(obj)
    if not isinstance(data, dict) or not data:
        raise VapixError(t("Sicherungsdatei enthaelt keine Konfigurationsdaten."))
    return data


def import_device_settings(ip, username, password, data, import_type="merge",
                           scheme="auto", port=None, timeout=120):
    """Spielt eine Geraete-Sicherung ein (DCA ``$import`` per PATCH).

    ``data`` ist die Ressourcen-Map (aus load_device_settings_backup) oder eine
    volle ``$export``-Antwort. ``import_type``:
      * ``"merge"``   — fehlende Werte behalten (nur Gesichertes ueberschreiben),
      * ``"default"`` — betroffene APIs zuruecksetzen, Fehlendes auf Standard.
    Das Geraet kann sich nach dem Einspielen selbst neu starten.
    """
    if import_type not in IMPORT_TYPES:
        raise ValueError("import_type muss 'merge' oder 'default' sein.")
    payload_data = _unwrap_backup(data)
    if not isinstance(payload_data, dict) or not payload_data:
        raise VapixError(t("Sicherung enthaelt keine Konfigurationsdaten."))
    body = {"data": payload_data, "options": {"importType": import_type}}
    try:
        resp = _post_json_auto(ip, username, password, DEVICE_SETTINGS_IMPORT_PATH,
                               body, scheme, port, timeout, method="PATCH")
    except VapixError as exc:
        if "404" in str(exc):
            raise VapixError(t("Geraet unterstuetzt keine Geraete-Sicherung "
                               "(benoetigt AXIS OS 11.8 oder neuer)."))
        raise
    if isinstance(resp, dict) and resp.get("status") == "error":
        raise VapixError(_dca_error(resp))
    return len(payload_data)


# --- Zeitzone (Time API, AXIS OS 9.30+) -------------------------------------
# Die Time API (POST /axis-cgi/time.cgi, JSON) ersetzt den in AXIS OS 13 entfernten
# param.cgi-Parameter ``Time.POSIXTimeZone``. ``setTimeZone`` nutzt IANA-Namen (z. B.
# ``Europe/Berlin``) und wendet die Sommerzeit-Regeln automatisch an; ``getAll`` liefert
# die aktuelle Zone und die vom Geraet unterstuetzten Zonen.
TIME_API_PATH = "/axis-cgi/time.cgi"


def _time_api(ip, username, password, method, params=None, scheme="auto", port=None, timeout=10):
    """Ruft eine Time-API-Methode auf und liefert die JSON-Antwort (Dict); wirft
    VapixError, wenn das Geraet ein ``error``-Objekt zurueckmeldet."""
    body = {"apiVersion": "1.0", "context": "kkm", "method": method}
    if params is not None:
        body["params"] = params
    resp = _post_json_auto(ip, username, password, TIME_API_PATH, body, scheme, port, timeout)
    if isinstance(resp, dict) and resp.get("error"):
        err = resp["error"]
        msg = (err.get("message") or err.get("code")) if isinstance(err, dict) else err
        raise VapixError(t("Geraet meldete Fehler: {msg}", msg=msg))
    return resp if isinstance(resp, dict) else {}


def get_time_settings(ip, username, password, scheme="auto", port=None, timeout=10):
    """Time API ``getAll`` -> ``data``-Dict (u. a. ``timeZone`` (IANA-Name),
    ``posixTimeZone``, ``dstEnabled``, ``timeZones`` = unterstuetzte Zonen)."""
    data = _time_api(ip, username, password, "getAll", None, scheme, port, timeout).get("data")
    return data if isinstance(data, dict) else {}


def get_timezone(ip, username, password, scheme="auto", port=None, timeout=10):
    """Aktuelle IANA-Zeitzone der Kamera (leer, wenn nicht gesetzt/verfuegbar)."""
    return get_time_settings(ip, username, password, scheme, port, timeout).get("timeZone") or ""


def list_timezones(ip, username, password, scheme="auto", port=None, timeout=10):
    """Vom Geraet unterstuetzte IANA-Zeitzonen (die Time API liefert sie selbst)."""
    return list(get_time_settings(ip, username, password, scheme, port, timeout).get("timeZones") or [])


def set_timezone(ip, username, password, timezone, scheme="auto", port=None, timeout=10):
    """Setzt die Zeitzone ueber die Time API (``setTimeZone``, IANA-Name; AXIS OS 9.30+).

    Ersetzt den in AXIS OS 13 entfernten param.cgi-Parameter ``Time.POSIXTimeZone``; die
    Sommerzeit wird anhand des IANA-Namens automatisch angewandt.
    """
    tz = (timezone or "").strip()
    if not tz:
        raise VapixError(t("Keine Zeitzone angegeben."))
    _time_api(ip, username, password, "setTimeZone", {"timeZone": tz}, scheme, port, timeout)
    return t("Zeitzone auf {tz} gesetzt", tz=tz)
