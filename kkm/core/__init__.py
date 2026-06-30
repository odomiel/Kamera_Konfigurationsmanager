"""Vendor-agnostic core: plugin API, group store, password vault."""

from .plugins import VendorPlugin, PluginRegistry, Credentials, Capability
from .groups import GroupStore, Group, ALL_CAMERAS_ID, camera_key
from .vault import PasswordVault, VaultLocked, VaultError
from .settings import AppSettings

__all__ = [
    "VendorPlugin", "PluginRegistry", "Credentials", "Capability",
    "GroupStore", "Group", "ALL_CAMERAS_ID", "camera_key",
    "PasswordVault", "VaultLocked", "VaultError",
    "AppSettings",
]
