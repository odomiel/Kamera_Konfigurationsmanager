# Drittanbieter-Lizenzen

Das ausgelieferte AppImage (Linux) bzw. die `.exe` (Windows) des
**Kamera_Konfigurationsmanagers** bündelt die unten aufgeführten Komponenten. Der
eigene Programmcode (Paket `kkm/`, `main.py`, `bump_version.py`,
`build_appimage.sh`) steht unter der **GPL-3.0-or-later** (siehe `LICENSE`).

## Übersicht

| Komponente | Version | Lizenz | Im Bundle |
|---|---|---|---|
| CPython | 3.14.x | PSF License Agreement | AppImage + .exe |
| Expat (libexpat) | in CPython | MIT | AppImage + .exe |
| Tcl | 9.0.x | Tcl/Tk License (BSD-artig) | AppImage (Quelltext) + .exe (aus Python 3.14) |
| Tk | 9.0.x | Tcl/Tk License (BSD-artig) | AppImage (Quelltext) + .exe (aus Python 3.14) |
| libffi | 3.6.0 | libffi License (MIT-artig) | AppImage |
| OpenSSL | 3.5.x | Apache License 2.0 | AppImage (ssl-Modul) |
| zeroconf | aktuell | **LGPL-2.1-or-later** | AppImage + .exe |
| ifaddr | aktuell | MIT | AppImage + .exe |
| cryptography | aktuell | Apache-2.0 **ODER** BSD-3-Clause | AppImage + .exe |
| cffi | aktuell | MIT | AppImage + .exe |
| pycparser | aktuell | BSD-3-Clause | AppImage + .exe |
| sv-ttk (Sun Valley) | aktuell | MIT | AppImage + .exe |

> Die genauen Versionen der Wheels (zeroconf, ifaddr, cryptography, cffi,
> pycparser) werden zur Bauzeit von PyPI in ihrer jeweils aktuellen Fassung
> gezogen; Tcl/Tk/Python/OpenSSL/libffi sind in `build_appimage.sh` gepinnt
> (`TCL_VER`/`TK_VER`/`PY_VER`/`SSL_VER`/`FFI_VER`). Diese Tabelle bei einem
> Versionswechsel aktualisieren.

> **Hinweis zu zeroconf (LGPL-2.1-or-later):** Alle übrigen Komponenten sind
> permissiv lizenziert. `zeroconf` steht unter der LGPL (schwaches Copyleft).
> Beim Verteilen muss der LGPL-Lizenztext beiliegen und es muss möglich sein,
> `zeroconf` durch eine eigene Version zu ersetzen — beim AppImage über
> `./Kamerakonfigurationsmanager-x86_64.AppImage --appimage-extract`, Austausch
> der Dateien und erneutes Packen. Quellcode:
> https://github.com/python-zeroconf/python-zeroconf

---

## CPython 3.14

Copyright © 2001-2025 Python Software Foundation. Alle Rechte vorbehalten.

Lizenziert unter dem **PSF License Agreement** (BSD-kompatibel, permissiv).
Vollständiger Text: https://docs.python.org/3/license.html

---

## Expat (libexpat)

Copyright © 1998-2000 Thai Open Source Software Center Ltd und Clark Cooper,
© 2001-2025 die Expat-Maintainer.

Lizenziert unter der **MIT-Lizenz** (Wortlaut wie bei *ifaddr* unten). Ein
schneller XML-Parser, der **in CPython** enthalten ist (C-Modul `pyexpat`) und dort
`xml.etree.ElementTree` zugrunde liegt. Das Programm nutzt ihn zum Parsen der
Kamera-Antworten: ONVIF-SOAP (`kkm/plugins/onvif`), Hikvision ISAPI/SADP
(`kkm/plugins/hikvision`) und Axis-VAPIX (`kkm/plugins/axis`). Quellcode:
https://github.com/libexpat/libexpat

---

## Tcl 9.0.4 und Tk 9.0.4

This software is copyrighted by the Regents of the University of California, Sun
Microsystems, Inc., Scriptics Corporation, ActiveState Corporation, Apple Inc.
and other parties. The following terms apply to all files associated with the
software unless explicitly disclaimed in individual files.

The authors hereby grant permission to use, copy, modify, distribute, and license
this software and its documentation for any purpose, provided that existing
copyright notices are retained in all copies and that this notice is included
verbatim in any distributions. No written agreement, license, or royalty fee is
required for any of the authorized uses.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES, INCLUDING, BUT
NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A
PARTICULAR PURPOSE, AND NON-INFRINGEMENT. THIS SOFTWARE IS PROVIDED ON AN "AS IS"
BASIS.

---

## libffi 3.6.0

libffi - Copyright (c) 1996-2024 Anthony Green, Red Hat, Inc and others.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the ``Software''), to deal in
the Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, subject to the inclusion of the above copyright notice. THE SOFTWARE IS
PROVIDED ``AS IS'', WITHOUT WARRANTY OF ANY KIND.

---

## OpenSSL 3.5.x

Copyright © 1998-2025 The OpenSSL Project Authors. Alle Rechte vorbehalten.

Lizenziert unter der **Apache License, Version 2.0**. Vollständiger Text:
https://www.apache.org/licenses/LICENSE-2.0 . Quellcode:
https://github.com/openssl/openssl

Wird im AppImage als `libssl`/`libcrypto` gebündelt und vom Python-`ssl`-Modul
für HTTPS-Verbindungen zu den Kameras (VAPIX-API) genutzt.

---

## zeroconf

Copyright © 2003 Paul Scott-Murphy, 2014 William McBrine, Jakub Stasiak und
weitere Mitwirkende.

Lizenziert unter der **GNU Lesser General Public License, Version 2.1 oder später
(LGPL-2.1-or-later)**. Vollständiger Text:
https://www.gnu.org/licenses/old-licenses/lgpl-2.1.html . Quellcode:
https://github.com/python-zeroconf/python-zeroconf

Wird für die mDNS-/Zeroconf-Discovery der Axis-Kameras genutzt.

---

## ifaddr

Copyright © 2014 Stefan C. Müller.

Lizenziert unter der **MIT-Lizenz**:

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in the
Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, subject to the inclusion of the above copyright notice. THE SOFTWARE IS
PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

Abhängigkeit von zeroconf.

---

## cryptography

Copyright © Individual contributors of the Python Cryptographic Authority (PyCA).

Lizenziert wahlweise unter der **Apache License 2.0** ODER der
**BSD-3-Clause-Lizenz** (Dual-Lizenz). Vollständige Texte:
https://www.apache.org/licenses/LICENSE-2.0 bzw.
https://github.com/pyca/cryptography/blob/main/LICENSE.BSD . Quellcode:
https://github.com/pyca/cryptography

Liefert AES-256-GCM für den Passwort-Tresor (`kkm/core/vault.py`). Das Wheel
enthält ein gebündeltes Krypto-Backend (statisch eingebaute OpenSSL-Bibliothek
der Rust-Erweiterung), unabhängig vom oben genannten System-/AppImage-OpenSSL.

---

## cffi

Copyright © Armin Rigo, Maciej Fijalkowski und weitere Mitwirkende.

Lizenziert unter der **MIT-Lizenz** (Wortlaut wie bei *ifaddr* oben). Quellcode:
https://github.com/python-cffi/cffi . Abhängigkeit von cryptography (nutzt das
oben gebündelte libffi).

---

## pycparser

Copyright © 2008-2022 Eli Bendersky und weitere Mitwirkende.

Lizenziert unter der **BSD-3-Clause-Lizenz**. Quellcode:
https://github.com/eliben/pycparser . Abhängigkeit von cffi.

---

## sv-ttk (Sun Valley ttk theme)

Copyright © rdbende und weitere Mitwirkende.

Lizenziert unter der **MIT-Lizenz** (Wortlaut wie bei *ifaddr* oben). Quellcode:
https://github.com/rdbende/Sun-Valley-ttk-theme bzw.
https://github.com/rdbende/sv-ttk . Liefert das moderne Hell/Dunkel-Design der
Oberfläche (reines Tcl-Theme, als Paketdaten gebündelt).
