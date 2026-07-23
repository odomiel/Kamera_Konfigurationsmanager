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

"""Tiny stdlib-only i18n layer (German source string = message id).

The whole app is authored in German; ``t("Einstellungen")`` returns the German
text verbatim when the active language is ``"de"`` and looks up an English
translation when it is ``"en"``. A missing translation falls back to the German
source, so the app is never blank — translating is purely additive. This keeps
the German dict keys / persistence identifiers (``FIELD_NAMES`` etc.) untouched:
only *display* text goes through :func:`t`.

The active language is a process-global set once at startup from the persisted
setting (:func:`set_language`), before any UI is built. There is no live
re-labelling of existing Tk widgets — a language change takes effect on the next
program start (same contract as "start maximized").

Catalogs are plain dicts in :mod:`kkm.core.i18n_catalog` (no gettext/.po
toolchain, matching the rest of the project).
"""

from __future__ import annotations

from .i18n_catalog import CATALOG

# Languages offered in the settings dialog: (code, native label).
LANGUAGES: list[tuple[str, str]] = [("de", "Deutsch"), ("en", "English")]
DEFAULT_LANGUAGE = "de"

_lang = DEFAULT_LANGUAGE


def set_language(lang: str | None) -> None:
    """Set the active UI language (``"de"``/``"en"``); unknown -> default."""
    global _lang
    codes = {code for code, _ in LANGUAGES}
    _lang = lang if lang in codes else DEFAULT_LANGUAGE


def get_language() -> str:
    return _lang


def language_label(code: str) -> str:
    for c, label in LANGUAGES:
        if c == code:
            return label
    return code


def t(text: str, /, **kwargs) -> str:
    """Translate ``text`` into the active language.

    German (source language) returns the text as-is. Optional ``kwargs`` are
    applied with :meth:`str.format` *after* the lookup, so message ids use named
    placeholders (``t("{n} Gerät(e)", n=n)``) and both language variants share
    the same placeholders.
    """
    if _lang == DEFAULT_LANGUAGE:
        out = text
    else:
        out = CATALOG.get(_lang, {}).get(text, text)
    if kwargs:
        try:
            return out.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return out
    return out
