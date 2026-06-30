"""Front-view action dialogs (one per former Kameraeinstellungen tab)."""

from kkm.core import Capability
from .config_dialog import ConfigDialog
from .firmware_dialog import FirmwareDialog

# Maps a Capability to the dialog that handles it. The main window looks the
# action up here; future actions (IP/Users/ONVIF) register the same way.
ACTION_DIALOGS = {
    Capability.CONFIG: ConfigDialog,
    Capability.FIRMWARE: FirmwareDialog,
}

__all__ = ["ACTION_DIALOGS", "ConfigDialog", "FirmwareDialog"]
