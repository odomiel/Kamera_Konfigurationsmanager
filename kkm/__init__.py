"""Kamera_Konfigurationsmanager — plugin-based multi-vendor camera config manager.

Top-level package. The application is structured in three layers:

- ``kkm.core``    — vendor-agnostic core (group store, password vault, plugin API).
- ``kkm.plugins`` — vendor plugins. Currently only ``axis`` (wraps a copied,
                    independently maintained VAPIX layer from the Discovery tool).
- ``kkm.gui``     — the Tkinter front-end (group tree + device table + action toolbar).
"""

from .version import __version__, APP_NAME

__all__ = ["__version__", "APP_NAME"]
