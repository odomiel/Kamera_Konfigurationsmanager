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

"""Minimal stdlib-only HTTPS client for the Senstar (Aimetis) Thin Client.

Stufe 1 (Anzeige) braucht nur eine **unauthentifizierte Kennung** des Geraets: der
Thin Client (Software 3.x) liefert auf jede unbekannte URL eine 404-Seite, die in der
Kopfleiste ``Senstar <Modell> Thin Client`` und die Softwarefassung nennt. Das reicht,
um das Geraet zu erkennen und Modell/Version anzuzeigen — **ohne jeden Loginversuch**
(wichtig beim Subnetz-Scan, damit keine Anmeldeversuche gegen fremde Geraete laufen).

Die 3.10-REST-API (Token-Login ueber ``POST /Session`` mit ``{"user","pwd"}`` -> Token
im Body, danach als Cookie ``authtoken``; Endpunkte ``/Settings``, ``/System/...``,
``/User``, kartiert aus ``server.js`` des Geraets) bleibt Stufe 2 vorbehalten und ist
hier bewusst noch nicht umgesetzt.
"""

from __future__ import annotations

import json
import re
import socket
import ssl
import urllib.error
import urllib.request
import uuid
import warnings

# Das Geraet spricht nur HTTPS (HTTP leitet dorthin um) mit selbstsigniertem
# Zertifikat -> Pruefung aus (wie die anderen Plugins fuer LAN-HTTPS).
_SSL = ssl.create_default_context()
_SSL.check_hostname = False
_SSL.verify_mode = ssl.CERT_NONE

# Aeltere Firmware spricht nur **veraltetes TLS** (TLS 1.0) mit „unsicherer" Legacy-
# Renegotiation; der moderne OpenSSL lehnt das sonst mit UNSUPPORTED_PROTOCOL bzw.
# UNSAFE_LEGACY_RENEGOTIATION_DISABLED ab. Dieser nachgiebige Context erlaubt es, damit
# auch solche Geraete (nur im LAN, Zertifikat ohnehin ungeprueft) erreichbar bleiben —
# **weiter verschluesselt** (kein Klartext-HTTP). Genutzt nur als Rueckfall, wenn der
# strikte Context an einem SSL-Fehler scheitert (:func:`_oeffnen`), damit neuere
# Firmware auf starkem TLS bleibt.
_SSL_LEGACY = ssl.create_default_context()
_SSL_LEGACY.check_hostname = False
_SSL_LEGACY.verify_mode = ssl.CERT_NONE
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)  # TLSv1 ist deprecated
    try:
        _SSL_LEGACY.minimum_version = ssl.TLSVersion.TLSv1
    except (ValueError, AttributeError):  # pragma: no cover
        pass
try:
    _SSL_LEGACY.set_ciphers("DEFAULT@SECLEVEL=0")
except ssl.SSLError:  # pragma: no cover
    pass
if hasattr(ssl, "OP_LEGACY_SERVER_CONNECT"):
    _SSL_LEGACY.options |= ssl.OP_LEGACY_SERVER_CONNECT

PORT = 443


def _oeffnen(req: urllib.request.Request, timeout: float):
    """``urlopen`` mit TLS-Rueckfall: erst der strikte Context, bei einem SSL-Fehler
    (veraltetes TLS aelterer Firmware) noch einmal mit dem nachgiebigen Legacy-Context.
    Eine echte HTTP-Antwort (``HTTPError``, z. B. 401/404) reicht der Aufrufer wie bisher
    durch; nur SSL-Handshake-Fehler loesen den Rueckfall aus."""
    for ctx in (_SSL, _SSL_LEGACY):
        try:
            return urllib.request.urlopen(req, context=ctx, timeout=timeout)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            letzter = not isinstance(getattr(exc, "reason", None), ssl.SSLError) \
                or ctx is _SSL_LEGACY
            if letzter:
                raise

# „Senstar A10D Thin Client" (Marke, dann Modell). Aeltere Firmware traegt noch den
# alten Markennamen „Aimetis" (vor der Senstar-Uebernahme) — beide zaehlen. Die
# Softwarefassung steht in der Kopfleiste *hinter* dieser Zeile und wird darum erst im
# Text NACH dem Modell-Treffer gesucht (sonst faengt man die jquery-ui-1.12.1 der Seite).
_MODELL = re.compile(r"(Senstar|Aimetis)\s+(\S+)\s+Thin\s+Client", re.I)
_FASSUNG = re.compile(r"(\d+\.\d+\.\d+(?:\.\d+)?)")

#: Ports, auf denen der Thin Client die Kennungs-Seite ausliefert. Neuere Firmware
#: nur HTTPS (443); aeltere spricht nur veraltetes TLS (vom modernen OpenSSL
#: abgelehnt) und liefert die Seite ueber HTTP (80). Fuer den *unauthentifizierten*
#: Fingerprint (keine Zugangsdaten) ist der HTTP-Rueckfall unbedenklich.
_KENNUNG_PORTS = (PORT, 80)


def erreichbar(ip: str, timeout: float = 0.4) -> bool:
    """Schneller TCP-Vortest auf den HTTPS-Port (vor dem teureren GET). Auch die
    aeltere Firmware (nur veraltetes TLS) haelt 443 offen — den HTTP-Rueckfall macht
    erst :func:`kennung`, damit der Subnetz-Scan nicht pro Fremdhost zweimal wartet."""
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, PORT)) == 0
    except OSError:
        return False
    finally:
        s.close()


def kennung(ip: str, timeout: float = 4.0) -> dict | None:
    """Erkennt einen Senstar Thin Client unauthentifiziert anhand seiner 404-Seite.

    Liefert ``{"modell", "version", "name"}`` oder ``None``, wenn es keiner ist /
    nicht antwortet. Rein lesend (ein GET), kein Loginversuch.
    """
    for port in _KENNUNG_PORTS:
        schema = "https" if port == PORT else "http"
        url = f"{schema}://{ip}:{port}/kkm-sondierung"
        req = urllib.request.Request(url, headers={"Accept": "text/html"})
        try:
            with _oeffnen(req, timeout) as resp:
                roh = resp.read(8192)
        except urllib.error.HTTPError as exc:      # 404 ist der Normalfall -> Body lesen
            try:
                roh = exc.read(8192)
            except Exception:  # noqa: BLE001
                continue
        except Exception:  # noqa: BLE001 - veraltetes TLS / offline -> naechster Port
            continue
        text = roh.decode("utf-8", errors="replace")
        m = _MODELL.search(text)
        if not m:
            return None                             # antwortet, aber kein Thin Client
        marke, modell = m.group(1), m.group(2)
        mf = _FASSUNG.search(text, m.end())         # Fassung erst NACH der Modellzeile
        return {
            "modell": modell,
            "version": mf.group(1) if mf else "",
            "name": f"{marke} {modell} Thin Client",
        }
    return None


# --------------------------------------------------------------------------- #
# Authentifizierte REST-API (Stufe 2): Token-Login + Settings                 #
# --------------------------------------------------------------------------- #

class SenstarError(Exception):
    """Fehler beim Ansprechen des Thin Clients. ``auth_failed`` markiert 401/403,
    damit der Aktionsdialog eine erneute Passwortabfrage anbieten kann."""

    def __init__(self, nachricht, auth_failed=False):
        super().__init__(nachricht)
        self.auth_failed = auth_failed


def _anfrage(ip: str, methode: str, pfad: str, token: str | None = None,
             daten: bytes | None = None, timeout: float = 10.0):
    """Ein REST-Aufruf. Token (falls vorhanden) als Cookie ``authtoken`` — so macht
    es auch die Web-Oberflaeche. Liefert (status, body_bytes)."""
    kopf = {"Accept": "application/json"}
    if daten is not None:
        kopf["Content-Type"] = "application/json"
    if token:
        kopf["Cookie"] = f"authtoken={token}"
    url = f"https://{ip}:{PORT}{pfad}"
    req = urllib.request.Request(url, data=daten, method=methode, headers=kopf)
    try:
        with _oeffnen(req, timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001 - offline / TLS
        raise SenstarError(f"Nicht erreichbar: {exc}")


def anmelden(ip: str, benutzer: str, passwort: str, timeout: float = 10.0) -> str:
    """Meldet sich an und liefert den Session-Token (``Data.Token``).
    Wirft SenstarError (auth_failed) bei leerem Token / falschem Passwort."""
    daten = json.dumps({"user": benutzer, "pwd": passwort}).encode("utf-8")
    status, body = _anfrage(ip, "POST", "/Session", daten=daten, timeout=timeout)
    try:
        token = json.loads(body)["Data"]["Token"]
    except Exception:  # noqa: BLE001
        token = ""
    if not token:
        raise SenstarError("Anmeldung fehlgeschlagen (Benutzer/Passwort?).",
                           auth_failed=True)
    return token


def abmelden(ip: str, token: str, timeout: float = 5.0) -> None:
    """Session beenden (best-effort; Fehler werden geschluckt)."""
    try:
        _anfrage(ip, "DELETE", f"/Session/{token}", token=token, timeout=timeout)
    except SenstarError:
        pass


def einstellungen_lesen(ip: str, token: str, timeout: float = 10.0) -> list[dict]:
    """Die vollstaendige Settings-Liste (``[{"Name","Value"}, …]``)."""
    status, body = _anfrage(ip, "GET", "/Settings", token=token, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status != 200:
        raise SenstarError(f"Einstellungen nicht lesbar (HTTP {status}).")
    try:
        return json.loads(body)["Data"]
    except Exception:  # noqa: BLE001
        raise SenstarError("Antwort auf /Settings nicht lesbar.")


def einstellungen_schreiben(ip: str, token: str, aenderungen: dict,
                            timeout: float = 15.0) -> None:
    """Read-modify-write: liest alle Settings, ueberschreibt die genannten Namen und
    schreibt die ganze Liste zurueck. Passwortfelder kommen vom Geraet maskiert als
    ``"noop"`` und bleiben so unveraendert — darum ist das Zurueckschreiben sicher."""
    liste = einstellungen_lesen(ip, token, timeout)
    offen = dict(aenderungen)
    for eintrag in liste:
        if eintrag.get("Name") in offen:
            eintrag["Value"] = offen.pop(eintrag["Name"])
    # Unbekannte Namen als zusaetzliche Eintraege anhaengen (sollte nicht vorkommen).
    for name, wert in offen.items():
        liste.append({"Name": name, "Value": wert})
    daten = json.dumps(liste).encode("utf-8")
    status, body = _anfrage(ip, "POST", "/Settings", token=token, daten=daten,
                            timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status not in (200, 201, 204):
        raise SenstarError(f"Einstellungen nicht speicherbar (HTTP {status}): "
                           f"{body[:200].decode(errors='replace')}")


def werksreset(ip: str, token: str, timeout: float = 15.0) -> None:
    """Setzt das Geraet auf Werkseinstellungen zurueck (``GET /System/Restore``);
    es startet danach neu. Setzt ALLES zurueck (kein „IP behalten")."""
    status, _ = _anfrage(ip, "GET", "/System/Restore", token=token, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status not in (200, 201, 202, 204):
        raise SenstarError(f"Werksreset fehlgeschlagen (HTTP {status}).")


# --------------------------------------------------------------------------- #
# Benutzer (Capability.USERS)                                                 #
# --------------------------------------------------------------------------- #

# Privilegien-Bits (aus der Geraete-Oberflaeche): ADMIN=1, PTZ_CONTROL=2, keine=0.
PRIV_ADMIN = 1
PRIV_NONE = 0


def benutzer_liste(ip: str, token: str, timeout: float = 10.0) -> list[dict]:
    status, body = _anfrage(ip, "GET", "/User", token=token, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status != 200:
        raise SenstarError(f"Benutzerliste nicht lesbar (HTTP {status}).")
    try:
        return json.loads(body)["Data"]
    except Exception:  # noqa: BLE001
        raise SenstarError("Antwort auf /User nicht lesbar.")


def _benutzer_schreiben(ip, token, methode, pfad, name, passwort, privilegien, timeout):
    daten = json.dumps({"Username": name, "Password": passwort,
                        "Privileges": privilegien}).encode("utf-8")
    status, body = _anfrage(ip, methode, pfad, token=token, daten=daten, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status not in (200, 201, 204):
        raise SenstarError(f"Benutzeraktion fehlgeschlagen (HTTP {status}): "
                           f"{body[:200].decode(errors='replace')}")


def benutzer_anlegen(ip: str, token: str, name: str, passwort: str,
                     admin: bool, timeout: float = 10.0) -> None:
    """Legt einen Benutzer an (``POST /User``). ``admin`` -> Rolle Administrator."""
    _benutzer_schreiben(ip, token, "POST", "/User", name, passwort,
                        PRIV_ADMIN if admin else PRIV_NONE, timeout)


def benutzer_loeschen(ip: str, token: str, name: str, timeout: float = 10.0) -> None:
    """Loescht einen Benutzer (``DELETE /User/<name>``)."""
    import urllib.parse
    pfad = "/User/" + urllib.parse.quote(name, safe="")
    status, body = _anfrage(ip, "DELETE", pfad, token=token, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status not in (200, 204):
        raise SenstarError(f"Benutzer löschen fehlgeschlagen (HTTP {status}).")


def benutzer_passwort(ip: str, token: str, name: str, passwort: str,
                      timeout: float = 10.0) -> None:
    """Setzt das Passwort eines bestehenden Benutzers (``PUT /User/<name>``).
    Die Privilegien bleiben erhalten (vorher gelesen -> kein Rollen-Downgrade)."""
    import urllib.parse
    priv = PRIV_NONE
    for u in benutzer_liste(ip, token, timeout):
        if u.get("Username") == name:
            priv = u.get("Privileges", PRIV_NONE)
            break
    else:
        raise SenstarError(f"Benutzer '{name}' nicht gefunden.")
    pfad = "/User/" + urllib.parse.quote(name, safe="")
    _benutzer_schreiben(ip, token, "PUT", pfad, name, passwort, priv, timeout)


# --------------------------------------------------------------------------- #
# Firmware (Capability.FIRMWARE): Datei hochladen + einspielen                #
# --------------------------------------------------------------------------- #

def _panel_stoppen(ip: str, token: str, groesse: int, timeout: float = 15.0) -> None:
    """Vor dem Upload die Anzeige stoppen und Platz reservieren (wie die UI:
    ``GET /Panel/Stop`` mit Kopf ``SizeOfFileUpload``). Fehler sind nicht fatal."""
    kopf = {"Accept": "application/json", "Cookie": f"authtoken={token}",
            "SizeOfFileUpload": str(groesse)}
    req = urllib.request.Request(f"https://{ip}:{PORT}/Panel/Stop", headers=kopf)
    try:
        with _oeffnen(req, timeout):
            pass
    except Exception:  # noqa: BLE001 - Anzeige-Stopp ist Komfort, kein Muss
        pass


def _server_kennung(ip: str, token: str, timeout: float = 8.0) -> str:
    """Server-Kopf des Geraets (``Server:``). Unterscheidet die aeltere Firmware
    (``Mono-HTTPAPI/…``) von der neueren (nginx) und damit den Upload-Weg."""
    req = urllib.request.Request(f"https://{ip}:{PORT}/System/Update/State",
                                 headers={"Accept": "application/json",
                                          "Cookie": f"authtoken={token}"})
    try:
        with _oeffnen(req, timeout) as resp:
            return resp.headers.get("Server", "")
    except urllib.error.HTTPError as exc:
        return exc.headers.get("Server", "")
    except Exception:  # noqa: BLE001
        return ""


def _firmware_put_upload(ip: str, token: str, pfad: str, groesse: int,
                         timeout: float) -> None:
    """Neuere Firmware: ``PUT /System/Update`` (octet-stream, gestreamt) ->
    ``POST /System/Update/FromFile`` (anwenden)."""
    with open(pfad, "rb") as fh:
        kopf = {"Accept": "application/json", "Cookie": f"authtoken={token}",
                "Content-Type": "application/octet-stream", "Content-Length": str(groesse)}
        req = urllib.request.Request(f"https://{ip}:{PORT}/System/Update", data=fh,
                                     method="PUT", headers=kopf)
        try:
            with _oeffnen(req, timeout) as resp:
                status = resp.status
        except urllib.error.HTTPError as exc:
            status = exc.code
        except Exception as exc:  # noqa: BLE001
            raise SenstarError(f"Firmware-Upload fehlgeschlagen: {exc}")
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status not in (200, 201, 204):
        raise SenstarError(f"Firmware-Upload abgelehnt (HTTP {status}).")
    # Anwenden anstossen (die UI ruft dies direkt nach dem Upload).
    status, body = _anfrage(ip, "POST", "/System/Update/FromFile", token=token,
                            timeout=60)
    if status not in (200, 201, 202, 204):
        raise SenstarError(f"Firmware-Anwendung abgelehnt (HTTP {status}): "
                           f"{body[:200].decode(errors='replace')}")


def _firmware_form_upload(ip: str, token: str, pfad: str, timeout: float) -> None:
    """Aeltere Firmware (Mono): Multipart-Form-Upload an ``POST /upload.html`` (Feld
    ``firmwareFile``) — so macht es die Geraete-Web-UI. Ergebnis im zurueckgegebenen
    Formular als verstecktes ``returnCode`` (``0`` = OK; der Upload spielt direkt ein,
    kein separater Anwenden-Schritt). Kennt die alte FW kein ``PUT /System/Update``."""
    import os
    grenze = "----kkm" + uuid.uuid4().hex
    name = os.path.basename(pfad) or "firmware.bin"
    kopf_teil = (f"--{grenze}\r\n"
                 f'Content-Disposition: form-data; name="firmwareFile"; '
                 f'filename="{name}"\r\n'
                 f"Content-Type: application/octet-stream\r\n\r\n").encode("utf-8")
    fuss_teil = f"\r\n--{grenze}--\r\n".encode("utf-8")
    with open(pfad, "rb") as fh:
        rumpf = kopf_teil + fh.read() + fuss_teil     # Firmware-Image komplett im RAM
    kopf = {"Accept": "text/html", "Cookie": f"authtoken={token}",
            "Content-Type": f"multipart/form-data; boundary={grenze}",
            "Content-Length": str(len(rumpf))}
    req = urllib.request.Request(f"https://{ip}:{PORT}/upload.html", data=rumpf,
                                 method="POST", headers=kopf)
    try:
        with _oeffnen(req, timeout) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001
        raise SenstarError(f"Firmware-Upload fehlgeschlagen: {exc}")
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status != 200:
        raise SenstarError(f"Firmware-Upload abgelehnt (HTTP {status}).")
    treffer = re.search(r'name="returnCode"\s+value="(-?\d+)"',
                        body.decode("utf-8", "replace"))
    code = treffer.group(1) if treffer else None
    # 0 = Erfolg. -1/kein Code = angestossen (Geraet startet neu, Verbindung faellt
    # weg) -> nicht als Fehler werten; andere negative Codes sind echte Fehler.
    if code not in (None, "0", "-1"):
        raise SenstarError(f"Firmware-Einspielung fehlgeschlagen (returnCode {code}).")


def firmware_einspielen(ip: str, token: str, pfad: str, timeout: float = 600.0) -> None:
    """Spielt eine Firmware-Datei ein. Vorgehen haengt von der Firmware ab: neuere
    (nginx) ueber ``PUT /System/Update`` + ``POST /System/Update/FromFile``, aeltere
    (Mono) ueber den Multipart-Form-Upload an ``/upload.html`` — die alte kennt das PUT
    nicht (403). Beide stoppen vorher die Anzeige (``GET /Panel/Stop``). Das Geraet
    installiert und startet danach neu."""
    import os
    groesse = os.path.getsize(pfad)
    _panel_stoppen(ip, token, groesse)
    if "Mono" in _server_kennung(ip, token):
        _firmware_form_upload(ip, token, pfad, timeout)
    else:
        _firmware_put_upload(ip, token, pfad, groesse, timeout)


def firmware_status(ip: str, token: str, timeout: float = 15.0) -> dict:
    """Fortschritt/Ergebnis des Updates (``GET /System/Update/State``):
    ``{"ExitCode": <None|int>, "Progress": <str>}``. ExitCode None = laeuft noch,
    0 = fertig/ok, sonst Fehlercode."""
    status, body = _anfrage(ip, "GET", "/System/Update/State", token=token,
                            timeout=timeout)
    if status != 200:
        return {"ExitCode": None, "Progress": ""}
    try:
        d = json.loads(body)["Data"]
        return {"ExitCode": d.get("ExitCode"), "Progress": d.get("Progress", "")}
    except Exception:  # noqa: BLE001
        return {"ExitCode": None, "Progress": ""}


def neueste_version(ip: str, token: str, timeout: float = 20.0) -> str:
    """Fragt das Geraet nach der online verfuegbaren neuesten Fassung
    (``GET /System/Update`` -> Versionsstring; leer, wenn keine/404)."""
    status, body = _anfrage(ip, "GET", "/System/Update", token=token, timeout=timeout)
    if status != 200:
        return ""
    try:
        return str(json.loads(body).get("Data", "") or "")
    except Exception:  # noqa: BLE001
        return ""


def ist_werksneu(ip: str, timeout: float = 5.0) -> bool:
    """True, wenn der Thin Client im Ersteinrichtungs-/Werkszustand ist.

    Im Werkszustand braucht der Einrichtungsassistent einen Token, obwohl noch kein
    Login existiert — daher gibt das Geraet dem **nicht angemeldeten** Besucher von
    ``GET /`` einen Setup-Token per ``Set-Cookie: authtoken=…`` mit. Ist das Geraet
    eingerichtet, vergibt ``GET /`` keinen solchen Cookie mehr (man muss sich
    anmelden). Dieser Unterschied ist der zuverlaessige Marker — die HTML-Shell
    selbst (inkl. ``wizard.js``) ist in beiden Zustaenden identisch, und Zustands-
    felder wie ``SetupWizardRun`` werden einem Gast maskiert.

    Rein lesend, unauthentifiziert, ohne Nebenwirkung. ``Accept: text/html`` ist
    noetig: bei ``application/json`` liefert das Geraet per Content-Negotiation die
    REST-Antwort — ohne den Setup-Cookie."""
    try:
        req = urllib.request.Request(f"https://{ip}:{PORT}/",
                                     headers={"Accept": "text/html"})
        with _oeffnen(req, timeout) as resp:
            if resp.status != 200:
                return False
            setze = resp.headers.get("Set-Cookie", "")
    except Exception:  # noqa: BLE001 - offline / kein Thin Client -> nicht werksneu
        return False
    return "authtoken=" in setze


def videoquellen_export(ip: str, token: str, timeout: float = 20.0) -> bytes:
    """Exportiert die Videoquellen-Liste des Geraets (``GET /Camera/Export``) als
    JSON-Bytes — die Datei, die die Web-Oberflaeche als ``cameras-<ts>.json``
    anbietet. Achtung: enthaelt die Zugangsdaten der Quellen im Klartext."""
    status, body = _anfrage(ip, "GET", "/Camera/Export", token=token, timeout=timeout)
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status != 200:
        raise SenstarError(f"Videoquellen-Export fehlgeschlagen (HTTP {status}).")
    return body


def videoquellen_import(ip: str, token: str, daten: bytes, timeout: float = 60.0) -> None:
    """Spielt eine Videoquellen-Liste ein. Die Web-Oberflaeche postet die Datei als
    Formular (``POST /import.html``, multipart-Feld ``camerasFile``) und liest den
    Ausgang aus dem zurueckgegebenen Formular (verstecktes ``returnCode``, 0 = OK) —
    genau so hier. Ein Import ist additiv/mergend (Abgleich ueber die Quellen-``Id``)."""
    grenze = "----kkm" + uuid.uuid4().hex
    rumpf = b"".join([
        (f"--{grenze}\r\n"
         f'Content-Disposition: form-data; name="camerasFile"; '
         f'filename="cameras.json"\r\n'
         f"Content-Type: application/json\r\n\r\n").encode("utf-8"),
        daten,
        f"\r\n--{grenze}--\r\n".encode("utf-8"),
    ])
    kopf = {"Accept": "text/html", "Cookie": f"authtoken={token}",
            "Content-Type": f"multipart/form-data; boundary={grenze}"}
    url = f"https://{ip}:{PORT}/import.html"
    req = urllib.request.Request(url, data=rumpf, method="POST", headers=kopf)
    try:
        with _oeffnen(req, timeout) as resp:
            status, body = resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001 - offline / TLS
        raise SenstarError(f"Nicht erreichbar: {exc}")
    if status in (401, 403):
        raise SenstarError("Nicht autorisiert.", auth_failed=True)
    if status != 200:
        raise SenstarError(f"Videoquellen-Import fehlgeschlagen (HTTP {status}).")
    treffer = re.search(r'name="returnCode"\s+value="(-?\d+)"',
                        body.decode("utf-8", "replace"))
    code = treffer.group(1) if treffer else None
    if code != "0":
        raise SenstarError("Videoquellen-Import fehlgeschlagen "
                           f"(returnCode {code if code is not None else '?'}).")
