# Help — Kamera_Konfigurationsmanager

This help describes all functions of the program. It is also available inside the
program via the **"Help"** button (top right).

The program manages and configures network cameras — **without** a live image.
Actions always apply to the cameras **selected** in the device list and run in the
background; the result per camera is logged.

Supported are **Axis** (full feature set) and, via a generic **ONVIF** plugin, cameras
from other manufacturers too (see the section "Plugins: Axis and ONVIF"). A detailed
**user manual** is included as `User_Manual.pdf`.

The interface is available in **German** and **English** (switchable under Settings →
"Appearance"; takes effect at the next program start). This help is shown in the
program language.

---

## Main window

- **Left:** the device groups. At the very top the non-deletable group
  **"All cameras"** (contains every known camera), directly below it the likewise
  permanent group **"Ungrouped"** (all cameras not yet assigned to a group of your own —
  e.g. newly found ones from a search; they disappear from there automatically as soon
  as they are assigned to a group), below that your own groups sorted **alphabetically**.
  To the right of the heading **"Device groups"** there is a **search field** (with the
  grey hint text "Search" that disappears as you type): while you type, the list is
  filtered live to groups whose name contains the search text (case-insensitive);
  "All cameras" always stays visible, an empty field shows all groups again. The divider
  between the left and right side can be moved, but not narrower than necessary so the
  group buttons stay readable.
- **Right:** the device list of the selected group, with the columns Name, Model,
  IP address, IPv6 address, MAC/serial no., Firmware, **Group(s)** and **Status**
  (online). IPv6 addresses are detected during the search (mDNS AAAA records or ONVIF
  XAddrs) and serve display purposes — the actions (IP, users, firmware …) still run
  over IPv4. A **click on a column header** sorts by that column (another click reverses
  the direction; ▲/▼ marks the active column). Sorting is "natural" — IP addresses and
  firmware versions order numerically. If the window is not wide enough for all columns
  (or not tall enough for all rows), a **scrollbar** appears automatically; the same
  applies to the group list on the left. **Column widths** can be changed by **dragging
  the column border** in the header; the chosen widths are kept across program starts.
- **Top:** the action bar (see below). If the window is not wide enough for all
  buttons (narrow window, small screen), only the **middle action buttons**
  (IP address through Time zone) become horizontally scrollable: a **◀** appears to
  the left of "IP address" and a **▶** to the right of "Time zone" for scrolling (an
  arrow is greyed out once that end is reached). The tools on the right (Settings,
  lock switch, Export) always **stay visible**. To the right of **"Settings"** there
  is a **lock switch**: **🔒** = vault locked, **🔓** = unlocked. A click toggles it —
  unlock (asks for the master password; creates a vault if needed) or lock the vault.

Multiple cameras can be selected with **Ctrl**/**Shift**.

**Open camera** — a **double-click** on a camera (or right-click → **"Open camera"**)
opens its web interface in the default browser (`http://<IP>`).

---

## Search & status

- **Search/refresh** — scans the local network for cameras (Axis: mDNS; with the ONVIF
  plugin active, additionally WS-Discovery) and adds them to "All cameras". Already known
  cameras are kept, even if they are currently offline.
  - The **arrow** on the right of the button opens the sub-item **"Add camera
    manually…"**: for cameras the search does not find (e.g. in a different subnet).
    The dialog asks for name, IP address, port, hostname and **manufacturer** (the
    manufacturer decides which plugin performs the actions). Right after adding, the
    IP is **contacted immediately**: if the camera is reachable, firmware/model are
    read and the factory state is detected — and credentials are requested if needed —
    just like after a search. The entry stays in the list permanently and is replaced
    automatically by a later search hit at the same IP (groups and stored credentials
    are carried over).
  - If the **ONVIF plugin** finds a camera that a manufacturer plugin (Axis) already
    reported, the ONVIF hit is discarded — otherwise the same camera would appear twice.
    The specialized plugin wins because it can do more.
  - **Firmware/model** are not part of the search result and are read afterwards via a
    camera login: cameras with known credentials (vault, or already entered in this
    session) are read out automatically.
  - **Factory-new cameras** (out-of-box state — no individual password set yet, or the
    factory default login still active) are detected automatically after the search and
    are **not** asked for a password; instead the **Firmware** column shows the note
    **"Initial setup required"**. Both new devices (AXIS OS 10/11, "create administrator
    account") and older ones with factory default credentials are recognized.
  - For cameras with **unknown credentials** a **prompt** appears (user/password). With
    the option **"Try this password on all cameras with unknown credentials"** the input
    is applied to all remaining cameras. Working credentials are **saved automatically**.
    If the vault is still locked/not yet created, you are **offered to set it up now**;
    if you decline, the credentials are only remembered for the current session. "Skip"
    leaves a camera out, "Cancel" ends the prompt.
- **Check online** — immediately checks the selected cameras (or the whole group) for
  reachability; the result appears in the **Status** column (● Online / ○ Offline).
- **Status after the search** — with every search, found cameras are set to **online**,
  known cameras that are no longer found to **offline**. In the status column **online is
  green**, **offline red**.
- **Automatic online check** — configurable per group (see Settings); the currently
  shown group is then checked at the configured interval.

---

## Groups

- **+ Group / Rename / Delete** (bottom left) — manage your own groups. "All cameras"
  cannot be renamed or deleted.
- **Assign a camera to a group** — select camera(s), **right-click** → **"Add to group"**
  → choose a group or **"New group…"**. A camera may be in several groups (additive).
- **Remove from a group** — inside one of your own groups via right-click →
  **"Remove from …"** (removes only the assignment, not the camera).
- **Remove a camera completely** — right-click → **"Remove camera(s) completely"**:
  deletes the camera from the device list and all groups, as well as its stored password.
  On the next search a reachable camera reappears.

---

## Credentials (in every action dialog)

Every action dialog has a **"Credentials"** area at the top: user, password, connection
(auto/https/http), optional port and timeout.

- **"Use credentials from the vault"** (checkbox, on by default as soon as a vault
  exists): for **every** camera the user **and** password are taken **first** from the
  password vault. The "user/password" fields are then greyed out and serve only as a
  **fallback** for cameras that do not (yet) have a vault entry. If the vault is still
  locked when the action starts, you are offered to unlock it.
- **Clearing the checkbox**: user/password are entered again and apply uniformly to
  **all** selected cameras (the vault is ignored).

This way you no longer have to type the password if it is stored in the vault.

**Password changed outside the program?** If a camera's password was changed elsewhere,
the stored vault entry no longer matches and the action fails with an authentication
error. The program detects this and, **after the run, asks once for the current
password** and **retries the action** for the affected camera(s). If several are
affected, it asks **once** and retries for all. When the vault is unlocked, the prompt
offers to **update the new password directly in the vault** (checkbox, on by default) —
so the prompt does not come back.

---

## Actions (buttons in the action bar)

The same seven actions (IP address, Users, ONVIF users, Firmware, Configuration,
Config backup, Time zone) are — where the plugin supports them — also available in the
**right-click menu** of the device list (which additionally offers "Reset to factory
defaults") and apply to the selected cameras there as well.

### IP address
Changes the network address of the selected cameras:
- **Switch to DHCP.**
- **Static IP consecutively** from a start IP — the addresses are assigned in order
  (shared subnet mask, optional gateway).
- **Per camera individually** — one IP field per camera (pre-filled with the current IP).

The target addresses are checked before the change; afterwards the cameras may be
reachable under a new address. For a static IP the **device list is updated to the new
address immediately on success** (only for successfully changed cameras). For DHCP the
displayed address stays unchanged, because the new address is assigned by the DHCP server
and is not known to the program.

Some cameras (e.g. older Hikvision/STD-CGI) only apply the change after a **restart** — the
program triggers it automatically and reports this in the result log.

### Users
Manage regular camera users:
- **Create** — name, password, role (administrator/operator/viewer). Option
  **Factory-default state (factory)** for brand-new cameras.
- **Change password** — set the password of an existing user.
- **Batch import** — user list from a file (`name,password[,role]`), applied to all
  selected cameras. The list may be a plain-text `.txt`/`.csv` **or** a
  **password-protected ZIP** (AES-256, e.g. created with 7-Zip/WinZip) — for a ZIP the
  archive password is prompted, so the plain-text passwords don't sit unprotected on disk.

The option **"Store password in the vault"** saves the credentials encrypted.

### ONVIF users
Like "Users", but for ONVIF accounts with the levels
**Administrator/Operator/User** (no factory-default state).

### Firmware
Updates the firmware of **several cameras of different models at once**:
- assign a matching firmware file per model — the file picker pre-filters by manufacturer
  (Axis/Dahua `.bin`, Hikvision `.dav`, Hanwha `.img`; "All files" stays available),
- option **Factory settings (factory default)**,
- models without an assigned file are skipped.

In the table the **"Current firmware"** column shows the currently installed version.
A **model row can be expanded** to see the individual cameras (with name, IP and current
firmware).

**Update search (Axis only).** The button **"Search for updates"** matches the models
against the manufacturer's public firmware directory. The **"Available (online)"** column
then shows per model:

- `11.11.212 ↑` — an update is available,
- `5.20.5 (current)` — the camera is up to date,
- `?` — the model was not found (then assign the file manually).

**"Download update and assign"** downloads the matching `.bin` with a progress indicator
and enters it as the model's firmware file — the rest of the process stays the same. The
download lands in a cache (clearable in the settings); an aborted download is resumed on
the next attempt.

The suggestion deliberately stays within the **camera's major version**: a camera on
10.12.x is offered the newest 10.12.x and does not jump to a new major-version branch
unasked. Via **"Select version…"** any other version of the model can be chosen
(including the newest overall). Can be turned off in the settings.

If cameras of a model are on **different** versions, the **newest** of them is the
comparison base — otherwise the suggestion would be a downgrade for the more up-to-date
camera (a model row gets exactly one file for all its cameras).

After the upload the program **waits** until the camera has restarted and is reachable
again, only then reports success and **reads out the new firmware version** and updates
it in the device list. The corresponding row in the dialog turns **green** on success
(the model row once all its cameras are done). If the *Factory settings* option is set,
the camera comes back factory-new and is marked as "Initial setup required".

Caution: the firmware must match the model; the cameras restart afterwards.

Some cameras (e.g. older Hikvision/STD-CGI) do not flash immediately but apply the uploaded
firmware only on the **next restart** — in that case the program triggers the restart itself
(otherwise it would wait endlessly "for the restart").

### Configuration (Axis `.cfg`)
Import/export of Axis Device Manager configuration files (format v1 + v2):
- **Import** — apply a `.cfg` to all selected cameras.
  - After choosing the file, the **selection of what to apply** opens: the individual
    parameters (searchable list with **"All"/"None"** and the toggle **"Show selected
    only"**), the **stream profiles individually** and the **motion detection (VMD4)**.
    Everything the file contains is preselected; a confirmation summarizes before writing
    what goes to how many cameras.
  - This is rarely just decoration: besides the image settings, a `.cfg` also contains
    the **network, name server and time server parameters of the source camera**. If you
    only want to roll out an image setting, filter the list e.g. by `Image.` and select
    only those parameters.
  - Write-protected `Properties.*` parameters (device properties that an AXIS Device
    Manager export writes along) are skipped automatically — otherwise the camera would
    reject the entire import with "Authentication failed" (HTTP 401).
  - **Parameters rejected by the device are skipped, not the whole import.** If the
    camera rejects individual parameters (e.g. ones removed/obsolete in newer firmware —
    AXIS OS 13 drops a number of them), only those are left out; the rest are applied and
    the skipped ones are named in the result log.
  - If the `.cfg` contains a **motion detection (VMD4)** — the AXIS Device Manager stores
    it as its own block, not as a `param.cgi` parameter — it is applied too via the VMD4
    app interface (`/local/vmd/control.cgi`). The file info then shows the note "Motion
    detection (VMD4)". If the VMD application on the camera is **stopped**, it is
    **started automatically** before applying (a stopped app would otherwise answer with
    "HTTP error 500"). Prerequisite: the target camera has the "AXIS Video Motion
    Detection" application installed (otherwise the import reports an error).
- **Export** — read out the configuration of the first selected camera and, in the
  **same selection** as for import, decide what goes into the `.cfg`: parameters,
  **stream profiles individually** and **motion detection (VMD4)**. The VMD4 option is
  only selectable if the camera has active motion detection (otherwise greyed out); the
  read-out does **not** start the VMD app by itself.
- **Reset to factory settings** — resets the selected cameras (they restart afterwards).
  Available options:
  - **Factory reset keeping the IP address** — all settings back, but the network/IP
    configuration is kept (the camera stays reachable at the same address). The program
    **waits** until the camera has restarted and is reachable again, and reports success
    only once it is back in **initial-configuration mode**; the device list then shows
    "Initial setup required".
  - **Complete factory reset (incl. IP address)** — the network settings are reset too
    (the camera falls back to the out-of-box state/DHCP). Since the IP changes, the
    camera then has to be found again via **Search**.

  A safety prompt has to be confirmed; the action cannot be undone. Credentials stored
  for the camera are discarded after the reset (they no longer apply).

### Config backup (whole-device backup)
Backs up or restores the **complete device configuration as a whole** — unlike the `.cfg`
template (selectable parameters), a device-specific full image (IP, name, event rules,
time, users …). Supported by **Axis**, **Hikvision**, **Dahua** and **Hanwha**.
- **Download backup (camera → file)** — reads the backup of the first selected camera and
  saves it. For Axis a **`.json` file** (the same one the web interface provides; without
  passwords), for the other manufacturers an encrypted **`.bin` blob**.
- **Restore backup (file → camera)** — transfers a backup file; the camera restarts
  afterwards. Because a backup contains device-specific data (IP, name), applying the same
  file to several cameras causes address/identity conflicts — the dialog warns about it.
  - **Axis** requires AXIS OS 11.8 or newer (Device Configuration API) and offers two
    variants: **Merge** (overwrite only saved values) or **Replace** (reset affected areas
    to defaults first). Restoring on Axis is not yet verified against real hardware; the
    dialog points this out.
  - **Hanwha** can **keep the target camera's network settings** (checkbox).

### Time zone
Sets the **time zone** of one or more cameras (Axis). It uses the **Time API** (from AXIS
OS 9.30) with **IANA names** such as `Europe/Berlin` — daylight saving is derived from that
automatically. This replaces the `Time.POSIXTimeZone` parameter removed from `param.cgi` in
**AXIS OS 13**.
- The time zone is picked from a **searchable list** (free entry possible).
- **"Load from first camera"** fetches the currently set time zone of the first selected
  camera and — if the device provides it — the list of zones it supports.
- **Apply** sets the chosen time zone on all selected cameras.

---

## Export
Saves the device list of the current group as **CSV** or **text file**.

---

## Plugins: Axis and ONVIF

The manufacturer-specific part sits in plugins. Which actions are possible is reported by
the respective plugin — unsupported buttons stay **greyed out**.

**Both plugins can:** device search (Axis via mDNS, ONVIF via WS-Discovery), online check
(with ONVIF even without credentials), read model/firmware, IP address (static/DHCP),
ONVIF users and factory reset.

**Only the Axis plugin can:** regular **users** (the ONVIF standard knows only *one* user
list — the ONVIF list), **install firmware**, the **update search**, the
**configuration import/export** (`.cfg`), the **config backup** (whole-device backup
via the Device Configuration API) and setting the **time zone** (Time API). For ONVIF
devices these buttons stay greyed out.

The **ONVIF plugin is off by default** (Settings → *Plugins*). It is meant for cameras
that have no dedicated manufacturer plugin; for Axis devices it simply can do less. The
ONVIF standard does not standardize a configuration template, the firmware update is
optional there and implemented differently per manufacturer, and there is no directory of
available firmware versions — hence the gaps above.

**Prerequisites:** ONVIF must be enabled on the camera and an **ONVIF user** must exist
(on Axis this is a **separate** user list — the regular credentials do not work for
ONVIF). In addition the **camera clock** should be correct: the ONVIF login is
time-dependent. The program compensates for the time offset itself, but a grossly wrong
date can still make the login fail.

---

## Settings
Several areas:
- **Appearance** — modern design **Dark** or **Light** (Sun Valley); the switch takes
  effect immediately and is saved. Via **"Language"** the program language can be switched
  between **German** and **English**; the choice is saved and takes effect **at the next
  program start** (not immediately — like the maximize option). Translated are the entire
  interface and the result messages of the actions; device-specific names (your own group
  names, model/firmware values) stay unchanged. In addition, **"Open maximized at
  startup"** can be enabled — the main window then opens full-screen at the next start.
- **Vault** — create, unlock, lock the password vault or change the master password. The
  vault stores camera passwords encrypted (AES-256-GCM, derived from the master password).
  - **"Unlock vault automatically at program start"** (checkbox): when enabled, the
    master password is asked once and stored **device-bound** (encrypted, tied to the
    computer + user account); after that the vault is unlocked immediately on every start.
    **Security note:** this is convenience at the expense of security — anyone with access
    to the computer as this user can open the vault. The token does not work on another
    computer/account. Clearing the checkbox deletes the token again.
- **Plugins** — enable/disable plugins: **Axis** (on) and **ONVIF (generic)** (off by
  default). The selection is saved.
- **Online check** — enable/disable the automatic online check per group and set the
  interval.
- **Columns** — show/hide individual columns of the device list (the "Name" column always
  stays visible).
- **Firmware updates** — two areas:
  - Switch **"Run firmware updates in parallel"**: if several cameras are selected, they
    are updated at the same time (up to the configurable **Maximum concurrent** number)
    instead of one after another. This shortens bulk updates considerably, since each
    camera's restart has to be waited for. If the switch is off, the updates run in
    sequence.
  - **Update search:** search online for updates (on/off); **"Keep the suggestion within
    the camera's major version"** (LTS-faithful, see the *Firmware* section); a custom
    **firmware directory** if an internal mirror is used (empty = the plugin's default);
    **"Clear firmware cache"** with a display of the used space.
- **Import and backup** — import devices and groups from an **AXIS Device Manager** export
  file (JSON) as well as create/restore your own backups. The file formats **1.x** and
  **2.x** are supported. Choose the file via "Choose export file and import…"; a preview
  shows version, number of devices/groups/credentials, then confirm. Devices are merged by
  MAC/serial number (no duplicate if they reappear later via a search), groups of the same
  name are **extended**. If the checkbox **"Import credentials into the vault"** is set and
  the vault is unlocked, the contained users/passwords are stored in the vault. Encrypted
  exports cannot be imported.

  In the same tab there is the **Backup (data + password vault)**:
  - **Export backup…** — writes groups, devices and the password vault into **one**
    encrypted file (`.kkmbackup`). A **backup password** is asked (twice), with which the
    file is protected via AES-256-GCM. The file can be re-imported cross-platform
    (Linux/Windows). **Keep the backup password safe** — without it the backup cannot be
    restored.
  - **Restore backup…** — restores a `.kkmbackup` file and **replaces** the current
    groups, devices and the vault. After restoring, the vault is locked and is unlocked
    with the **master password from the backup**. If the plugin selection changed, restart
    the program.

- **About** — shows the program version, the versions of the components used (Python,
  Tcl/Tk, zeroconf, cryptography, sv-ttk), the author and the license, as well as the note
  that the program was developed with the support of artificial intelligence. It also shows
  the **project page** as a clickable link and an **update check** (source: the public
  GitHub releases): "Check for updates now" reports a newer version with a download link;
  the option "Check for updates at startup" is on by default and **can be turned off**
  (nothing happens offline, pre-releases are ignored).

---

## Where the data is stored
Groups (`groups.json`), settings (`settings.json`) and the encrypted password vault
(`vault.enc`) are stored in the subfolder `kamera_konfigurationsmanager`:

- **Windows (portable `.exe`):** **next to the executable** — the configuration is thus
  portable (e.g. on a USB stick) and stays with the program.
- **Windows (started from source):** in the user profile under
  `%APPDATA%\kamera_konfigurationsmanager`.
- **Linux:** in the user profile under `~/.config/kamera_konfigurationsmanager`.

On Linux the folder is **accessible to your own user account only** (folder `0700`,
files `0600`); other users on the same computer can read neither the camera list nor
the vault or the auto-unlock token. Older installations are secured accordingly at
program start. Exported backups (`.kkmbackup`) are likewise created readable for your
own account only.
