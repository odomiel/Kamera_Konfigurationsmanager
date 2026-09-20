# User Manual

## 1 About this program

The **Kamera_Konfigurationsmanager** finds network cameras on the local network and
configures them — individually or many at once. Its layout is loosely based on the AXIS
Device Manager, **without a live image and without recording**: it is purely about
management and configuration.

All actions always apply to the cameras **selected** in the device list, run in the
background and log their result for **each camera individually**. The window stays usable
throughout; nothing blocks.

The interface is available in **German** and **English** (switchable in Settings →
*Appearance*, see chapter 12; the change takes effect at the next start). This manual is
available in German and English.

Two device families are supported:

- **Axis** — full feature set via the VAPIX interface.
- **ONVIF (generic)** — any standard-compliant camera, with the feature set that the
  ONVIF standard provides (see chapter 11). Off by default.

> **Note:** The program stores everything in plain files — no database, no server service,
> no cloud. It runs purely locally on your network.

## 2 Installation and start

### Linux (AppImage)

The AppImage is self-contained: it includes Python, Tcl/Tk and all libraries. Nothing
needs to be installed.

```
chmod +x Kamerakonfigurationsmanager-<version>-x86_64.AppImage
./Kamerakonfigurationsmanager-<version>-x86_64.AppImage
```

### Windows (portable .exe)

The file `Kamerakonfigurationsmanager_<version>.exe` is **not installed** but started
directly. It stores its data **next to itself** (folder `kamera_konfigurationsmanager`) —
program and configuration can thus be copied together onto a USB stick and used elsewhere.

### From source

```
pip install -r requirements.txt
python3 main.py
```

Requires Python 3.14 with Tkinter as well as the packages `zeroconf`, `cryptography` and
`sv-ttk`.

## 3 First steps

At startup a **disclaimer** appears first: this is not an official tool of the supported
manufacturers, use is at your own risk. With the checkbox *"I know what I'm doing – don't
show again"* it can be confirmed permanently; the same text is also found under
*Settings → About*.

The typical flow on first start:

1. Click **Search/refresh**. The program scans the local network and adds all found
   cameras to the "All cameras" group.
2. For cameras with unknown credentials a **prompt** appears. Enter user and password —
   with the option *"Try this password on all cameras with unknown credentials"* the input
   applies to all cameras still pending.
3. Working credentials are **saved automatically**. Since an encrypted vault is required
   for that, the program offers to set it up now (chapter 9). If you decline, it remembers
   the credentials only for the current session.
4. Only now does the program know **model and firmware** of each camera — neither is part
   of the search result but is read via a camera login.
5. Select cameras and choose an action from the bar at the top.

> **Factory-new cameras** are detected automatically and are **not** asked for a password.
> The *Firmware* column then shows "Initial setup required".

## 4 The main window

**On the left** are the device groups. At the very top the non-deletable group **"All
cameras"**, below it **"Ungrouped"** (all cameras without a group assignment of their own,
e.g. freshly found ones), below that your own groups alphabetically. The **search field**
next to the heading filters the group list live.

**On the right** is the device list of the selected group, with the columns *Name, Model,
IP address, IPv6 address, MAC/serial no., Firmware, Group(s)* and *Status*. IPv6 addresses
are detected during the search (global addresses first, link-local `fe80::` after them)
and serve display and export purposes — the actions themselves run over the IPv4 address.
A click on a column header sorts by it, another click reverses the direction (▲/▼ marks
the active column). Sorting is "natural", meaning IP addresses and firmware versions order
numerically and not alphabetically. You change the **column widths** by dragging the column
border in the header; the setting is kept across program starts. Which columns are visible
at all is set in the settings (chapter 12).

**At the top** is the action bar. To the right of *Settings* a lock switch shows the state
of the password vault: closed lock = locked, open lock = unlocked. A click toggles it. If
the window is too narrow for all buttons, only the middle action buttons (IP address
through Time zone) become horizontally scrollable — a **◀** to the left of *IP address*
and a **▶** to the right of *Time zone* scroll through them; the tools on the right
(Settings, lock, Export) always stay visible.

You select multiple cameras with **Ctrl** or **Shift**. A **double-click** on a camera
opens its web interface in the browser.

All seven actions (IP address, Users, ONVIF users, Firmware, Configuration, Config
backup, Time zone) are — where the plugin supports them — also available in the
**right-click menu** of the device list, which additionally offers *Reset to factory
defaults*.

## 5 Device search and online status

The search finds Axis cameras via **mDNS**; if the ONVIF plugin is also active, it searches
in parallel for ONVIF devices via **WS-Discovery**. Already known cameras are kept, even if
they are currently offline.

Found cameras are set to **online**, known ones that are no longer found to **offline**
(green respectively red in the *Status* column). **Check online** checks the selected
cameras immediately; in addition an **automatic online check** with an interval can be
enabled per group (chapter 12).

**Add a camera manually.** If the search does not find a camera — because it is in a
different subnet, or mDNS/WS-Discovery is blocked on the network — add it by hand via
the **arrow** on the right of the *Search/refresh* button and the sub-item *"Add camera
manually…"*. The dialog asks for **name, IP address, port, hostname** and the
**manufacturer**. The manufacturer matters: it determines which plugin talks to the
camera (Axis, ONVIF, Hikvision …) — without it the program would not know how to set
the IP address, users or firmware. The IP address is validated; an IP that is already
present is rejected. Right after adding, the program **contacts the IP immediately
(detection)**: it first checks reachability, and if the camera is online, the same
evaluation as after a search runs — firmware and model are read, the factory state is
detected, and the credential prompt appears if needed. If the IP is not reachable, the
camera stays as an offline entry (no password is requested). The entry stays in the
list permanently (across restarts too) and is replaced automatically by a later search
hit at the same IP — group assignment and stored credentials are carried over.

> **Duplicate entries?** If the Axis and ONVIF plugins are active at the same time, the
> ONVIF plugin also finds the Axis cameras. The program discards such hits automatically:
> if one of the IP addresses was already reported by a manufacturer plugin, that one wins
> because it can do more. If the same camera does end up in the list under both identities
> from earlier searches, the next search merges the entries by itself — group assignment,
> online status and stored credentials move to the manufacturer entry (the status line
> reports "… ONVIF duplicate(s) merged").

## 6 Groups

Groups are purely an organizational aid — a camera may be in several groups.

- **+ Group / Rename / Delete** (bottom left) manages your own groups. "All cameras" can be
  neither renamed nor deleted.
- **Assign:** select cameras, right-click → *"Add to group"* → choose a group or *"New
  group…"*.
- **Remove from a group** only releases the assignment, the camera stays known.
- **Remove camera(s) completely** deletes the camera from all groups **and** its stored
  password. On the next search a reachable camera reappears.

## 7 Credentials in the action dialogs

Every action dialog has the **Credentials** area at the top: user, password, connection
(auto/https/http), optional port and timeout.

If **"Use credentials from the vault"** is checked (the default as soon as a vault exists),
user and password are taken **per camera** from the vault. The fields at the top are then
greyed out and serve only as a **fallback** for cameras without a vault entry. If you clear
the checkbox, the entered credentials apply uniformly to all selected cameras.

**Password changed outside the program.** If the stored password no longer matches (the
action fails with an authentication error), the program **asks once for the current
password after the run** and **retries the action** for the affected cameras (if several
are affected, it asks once and retries for all). When the vault is unlocked, the prompt
offers to **update the new password in the vault** (checkbox, on by default) — so the
prompt does not come back.

## 8 The actions

### 8.1 IP address

Changes the network address of the selected cameras — either to **DHCP**, to a **static IP
consecutively from a start IP** (the addresses are assigned in order; the program
automatically skips network and broadcast addresses such as `x.y.z.0`/`x.y.z.255`) or
**per camera individually** (one field per camera, pre-filled with the current IP).

The target addresses are checked before the change. For a static IP the program updates the
device list to the new address immediately; for DHCP the displayed address remains, because
the new address comes from the DHCP server and is not known to the program — search again
afterwards.

> **Note:** Some cameras (e.g. older Hikvision/STD-CGI) only apply a switch to DHCP or a new
> static IP after a **restart** ("Reboot Required"). The program triggers that restart
> automatically; the result message then reads e.g. "switched to DHCP — restart triggered
> automatically".

### 8.2 Users

Manages the regular camera users: **Create** (name, password, role
*administrator/operator/viewer*, option *Factory-default state* for brand-new cameras),
**Change password** and **Batch import** from a file in the format
`name,password[,role]`. The file is validated once up front — if a line fails, nothing is
created at all. The source may be a plain-text `.txt`/`.csv` **or** a
**password-protected ZIP archive** (AES-256, e.g. created with 7-Zip or WinZip): if you
pick a ZIP, the program asks for its password and reads the contained text/CSV file
decrypted — so the users' plain-text passwords need not sit unprotected as a file.

The option *"Store password in the vault"* saves the credentials encrypted.

### 8.3 ONVIF users

Like *Users*, but for ONVIF accounts with the levels **Administrator/Operator/User**.

> **Important:** On Axis cameras, ONVIF users are a **separate list**, distinct from the
> regular users. Anyone who wants to use the ONVIF plugin needs an account here first —
> the VAPIX credentials do not get ONVIF in.

### 8.4 Firmware

Updates several cameras of **different models at the same time**. The cameras are grouped by
model; each model row gets **one** matching firmware file, and a row can be expanded to see
the individual cameras. Models without an assigned file are skipped. The file picker
pre-filters by manufacturer (Axis/Dahua `.bin`, Hikvision `.dav`, Hanwha `.img`; "All
files" stays available).

**Search for updates** (Axis only) matches the models online. The program reads the
manufacturer's public firmware directory and shows in the *Available (online)* column which
version exists:

- `11.11.212 ↑` — an update is available.
- `5.20.5 (current)` — the camera is up to date.
- `?` — the model was not found in the directory (then please assign the file manually).

**Download update and assign** downloads the matching file with a progress indicator and
enters it as the model's firmware file. The download lands in a cache; an aborted download
is resumed on the next attempt.

The suggestion deliberately stays within the **camera's major version**: a camera on 10.12.x
is offered the newest 10.12.x and not the jump to a new major-version branch. Via **Select
version…** you can take any other version of the model, including the newest overall. This
restraint can be turned off in the settings.

After the upload the program **waits** for the restart, reads out the new version and turns
the row green. If *Factory settings (factory default)* is checked, the camera comes back
factory-new and is marked as "Initial setup required".

> **Caution:** The firmware must match the model. The cameras restart after the update and
> are unreachable for a few minutes.

> **Note:** Some cameras (e.g. older Hikvision/STD-CGI) do not flash immediately — they only
> accept the uploaded firmware and apply it on the **next restart**. In that case the program
> triggers the restart itself; otherwise the camera would appear unchanged and the progress
> would wait endlessly "for the restart".

### 8.5 Configuration

Import and export of Axis configuration files (`.cfg`, format v1 and v2).

**Import** — choose a file, then the **selection** of what to apply opens: the individual
parameters (searchable list with *All*/*None* and the *Show selected only* view), the
**stream profiles individually** and the **motion detection (VMD4)**. Everything the file
contains is preselected.

> **Why select?** A `.cfg` contains not only image settings but also the network, name
> server and time server parameters of the source camera. Anyone who wants to roll out an
> image setting to twenty cameras rarely wants to send along their network configuration.
> Filter the list for example by `Image.` and select only those parameters.

Write-protected `Properties.*` parameters are skipped automatically — otherwise the camera
would reject the entire import with "Authentication failed". If the camera additionally
rejects **individual** parameters (e.g. ones removed/obsolete in newer firmware — AXIS OS 13
drops a number of them), only those are skipped and named in the result log; the rest of the
import goes through instead of failing entirely. A contained motion detection is applied via
the VMD4 interface; if the VMD application on the camera is stopped, the program starts it
beforehand.

**Export** — reads out the configuration of the **first** selected camera and opens the same
selection; afterwards the `.cfg` is saved.

**Reset to factory settings** — with two variants:

- **Keeping the IP address:** everything back, but the camera stays reachable at the same
  address. The program waits for the restart and reports success only once the camera is
  back in initial-configuration mode.
- **Complete factory reset:** the network settings fall back too. The camera is then
  reachable at a new address and has to be searched for again.

Both are **irreversible** and have to be confirmed. Credentials stored for the camera are
discarded afterwards because they no longer apply.

### 8.6 Config backup

Backs up or restores the **complete device configuration as a whole** — unlike the `.cfg`
template (section 8.5) with its parameter selection, a device-specific full image (IP,
name, event rules, time, users …). Supported by **Axis**, **Hikvision**, **Dahua** and
**Hanwha**.

- **Download backup (camera → file)** — reads the backup of the **first** selected camera
  and saves it. For Axis a **`.json` file** (the same one the web interface provides;
  passwords are not included), for the other manufacturers an encrypted **`.bin` blob**.
- **Restore backup (file → camera)** — transfers a backup; the camera restarts afterwards.
  Because a backup contains device-specific data (IP, name), applying the same file to
  several cameras causes address/identity conflicts — the dialog warns about it.
  - **Axis** requires AXIS OS 11.8 or newer (Device Configuration API) and offers the
    variants **Merge** (overwrite only saved values) or **Replace** (reset affected areas
    to defaults first). Restoring on Axis is not yet verified against real hardware; the
    dialog points this out.
  - **Hanwha** can **keep the target camera's network settings** (checkbox).

### 8.7 Time zone

Sets the **time zone** of one or more Axis cameras via the **Time API** (from AXIS OS 9.30)
using **IANA names** such as `Europe/Berlin`; daylight saving is derived from that
automatically. This replaces the `Time.POSIXTimeZone` parameter removed from `param.cgi` in
**AXIS OS 13**. The time zone is picked from a searchable list (free entry possible); **"Load
from first camera"** takes over the currently set time zone of the first selected camera
(and, if the device provides it, the list of supported zones). **Apply** sets it on all
selected cameras.

## 9 The password vault

The vault stores the camera passwords encrypted in **one** file (`vault.enc`): from your
**master password** a key is derived via PBKDF2, the data is stored encrypted with
**AES-256-GCM**. No operating-system keyring is used — the file is thus portable.

It is managed in the settings (tab *Vault*): create, unlock, lock, change the master
password. The lock switch at the top right of the main window does the same with one click.

**Unlock automatically** stores the master password **device-bound** (encrypted, tied to
the computer and user account), so the vault is open immediately on every start.

> **Security note:** This is convenience at the expense of security — anyone with access to
> the computer as this user can open the vault. On another computer or account the token
> does not work.

**Without the master password there is no way back.** There is no backdoor and no recovery.

## 10 Exporting the device list

**Export** saves the device list of the current group as **CSV** or as an aligned **text
file** — handy for documentation and handovers.

## 11 Plugins: Axis and ONVIF

The entire manufacturer-specific part sits in plugins. Which actions are possible is
reported by the respective plugin; unsupported buttons stay **greyed out**.

| Function | Axis | ONVIF (generic) |
| --- | --- | --- |
| Device search | mDNS | WS-Discovery |
| Online check | yes | yes (without credentials) |
| Read model / firmware | yes | yes |
| IP address (static/DHCP) | yes | yes |
| Users | yes | — (standard knows only one list) |
| ONVIF users | yes | yes |
| Install firmware | yes | — |
| Update search | yes | — |
| Configuration (.cfg) | yes | — |
| Config backup (whole-device) | yes | — |
| Time zone (Time API) | yes | — |
| Factory reset | yes | yes |

The ONVIF plugin is **off by default** and is enabled in the settings under *Plugins*. It is
meant for cameras that have no dedicated plugin — for Axis devices it simply can do less.

> **Experimental: Hikvision and Dahua.** In addition, two manufacturer plugins are included,
> both marked as **"experimental"** in the plugin manager, **off by default** and **not yet
> verified on real hardware** — the write actions follow the respective manufacturer
> documentation but should be used carefully and at your own risk:
>
> - **Hikvision** (ISAPI): search via SADP, device info, IP, users, ONVIF users, firmware
>   upload, **config backup**, factory reset. The SADP search also finds **factory-new**
>   cameras still on their **factory IP in a different IP segment** (e.g. `192.0.0.64` or
>   `192.168.1.64` while the computer is in `192.0.2.x`).
> - **Dahua** (HTTP API): search via DHIP, device info, IP, users, ONVIF users, firmware
>   upload, factory reset. Also covers many **Dahua OEM brands** — including the **Honeywell
>   Performance Series** and Amcrest.
> - **Hanwha/Wisenet** (SUNAPI): search via ONVIF, device info, IP, users, ONVIF users,
>   firmware, **config backup**, factory reset. Verified on a Wisenet camera (discovery,
>   info, IP, users); firmware and factory reset not yet.
>
> For all of them there is no update search and no `.cfg` **parameter** import/export (no
> open firmware directory, no cross-manufacturer configuration template). The **config
> backup** (opaque whole-device image, section 8.6) is independent of this and is available
> for Hikvision and Hanwha.

**What ONVIF cannot do and why:** the standard does not standardize a configuration template
(its backup function only returns an opaque data block for exactly one device), the firmware
update is optional in the standard and implemented very differently by the manufacturers,
and there is no directory of available firmware versions.

**Prerequisites for ONVIF:** ONVIF must be enabled on the camera and an **ONVIF user** must
exist. In addition the **camera clock** should be roughly correct — the ONVIF login is
time-dependent. (The program compensates for the time offset itself, but a grossly wrong
date can still make the login fail.)

## 12 Settings

**Appearance** — modern design **Dark** or **Light**; the switch takes effect immediately.
**Language** — the program language **German** or **English**; the choice is saved and takes
effect **at the next program start** (not immediately — like *Open maximized at startup*).
Translated are the entire interface and the result messages of the actions; device-specific
names (your own group names, model/firmware values) stay unchanged. In addition: *Open
maximized at startup*.

**Vault** — see chapter 9.

**Plugins** — enable and disable manufacturer plugins (Axis, ONVIF). The selection is saved.

**Online check** — enable/disable the automatic check per group and set the interval.

**Columns** — show and hide individual columns of the device list (*Name* always stays
visible).

**Firmware updates** — two areas:

- *Run firmware updates in parallel* (with **Maximum concurrent**): several selected cameras
  are updated at the same time instead of one after another. This shortens bulk updates
  considerably, because each camera's restart has to be waited for.
- *Update search*: search online on/off; **Keep the suggestion within the camera's major
  version** (see 8.4); a custom **firmware directory** if you run an internal mirror (empty =
  the manufacturer's default); **Clear firmware cache** together with a display of the used
  space.

**Import and backup**

- *Import from AXIS Device Manager:* imports devices and groups from an export file (JSON,
  format 1.x and 2.x). Devices are merged by MAC/serial number, groups of the same name are
  extended. Contained credentials move into the vault on request. Encrypted exports cannot be
  read.
- *Export backup:* writes groups, devices **and** the password vault into **one** encrypted
  file (`.kkmbackup`, protected by a separately requested backup password, AES-256-GCM). Can
  be re-imported cross-platform.
- *Restore backup:* restores a `.kkmbackup` and **replaces** the current data. Afterwards the
  vault is locked and is opened with the master password **from the backup**.

> **Keep the backup password safe** — without it the backup cannot be restored.

**About** — shows the program and component versions, the author and the license, as well as
the note about the AI-supported development. It also shows the **project page** as a
clickable link (opens the GitHub page in the browser). Below it, the **update check**:
*"Check for updates now"* queries the public GitHub releases and reports whether a newer
version is available (with a download link). The option *"Check for updates at startup"*
(on by default, can be turned off any time) checks in the background at startup and points
it out discreetly only when there really is a newer version; nothing happens without an
internet connection. Only final versions are considered, not pre-releases.

**Licenses** — lists, in a scrollable field, the licenses of **all bundled components**
(Python, Tcl/Tk, OpenSSL, zeroconf, cryptography, etc. — the third-party licenses) as well
as the **full GPL-3.0 license text** of the program itself.

## 13 Where the data is stored

Stored are the groups and the known device list (`groups.json`), the settings
(`settings.json`) and the encrypted vault (`vault.enc`) — each in the folder
`kamera_konfigurationsmanager`:

| Variant | Location |
| --- | --- |
| Windows (portable .exe) | **next to the .exe** — portable |
| Windows (from source) | `%APPDATA%\kamera_konfigurationsmanager` |
| Linux | `~/.config/kamera_konfigurationsmanager` |

Downloaded firmware is kept in the subfolder `firmware_cache` and can be cleared in the
settings at any time.

## 14 Troubleshooting

**"Authentication failed" (401).** User or password is wrong — or the vault provides an old
entry for this camera. Check the *Use credentials from the vault* checkbox and, if necessary,
enter the data directly. After a factory reset, old credentials no longer apply.

**The search does not find a known camera.** mDNS and WS-Discovery work with multicast and do
not cross network boundaries: cameras in another subnet (or behind a VPN) do not answer.
Already known cameras nevertheless stay in the list and can still be configured as long as
they are reachable by IP.

**Update search reports "model not found".** The model is named differently in the
manufacturer's firmware directory than the camera reports it. In that case download the file
yourself and assign it manually — the rest of the process stays the same.

**Update search reports a certificate problem.** The download deliberately verifies the HTTPS
certificate (it is a foreign file that is subsequently written onto the camera). If the
program finds no certificate store, it aborts instead of silently disabling the check.

**ONVIF reports "Sender not authorized" or a login error.** An ONVIF user is missing on the
camera (on Axis a separate list!), or the camera clock is grossly wrong.

**A camera appears twice in the list.** Axis/ONVIF doppelgangers of the same camera are
merged automatically on the next search (see chapter 5). If a duplicate remains, the same
camera is known under two different IPs (e.g. after a DHCP change) — remove the old entry via
*Remove camera(s) completely*.

**After the firmware update the camera "did not return in time".** The upload was successful,
the restart just took longer than the time window. Search again later or check the online
status.

## 15 Glossary

**mDNS** — a method with which devices announce themselves on the local network. The basis of
the Axis device search.

**WS-Discovery** — the counterpart in the ONVIF standard: the program queries the network via
multicast, ONVIF devices answer.

**VAPIX** — the programming interface of the Axis cameras. All Axis actions run over it.

**ONVIF** — a cross-manufacturer standard for network cameras. The program uses only the
device-management part of it, not the video part.

**VMD4** — the motion detection of Axis. In a `.cfg` it sits in its own block, not in the
normal parameters.

**LTS** — a firmware branch with long-term maintenance that only receives bug and security
fixes instead of new features.

**Capability** — a capability that a plugin reports (e.g. "can install firmware"). From them
follows which buttons are usable for a camera.

## 16 License

This program is free software under the **GNU General Public License, version 3 or later
(GPL-3.0-or-later)**. It contains parts of the tool *Axis_Kamera_Discovery*, which is also
under GPL-3.0.

The program was developed with the support of artificial intelligence.
