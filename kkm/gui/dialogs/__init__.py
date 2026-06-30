"""Front-view action dialogs (one per former Kameraeinstellungen tab)."""

from kkm.core import Capability
from .config_dialog import ConfigDialog
from .firmware_dialog import FirmwareDialog
from .user_dialog import UserDialog

# Maps a Capability to the dialog that handles it. The main window looks the
# action up here; remaining actions (ONVIF/IP) register the same way.
ACTION_DIALOGS = {
    Capability.CONFIG: ConfigDialog,
    Capability.FIRMWARE: FirmwareDialog,
    Capability.USERS: UserDialog,
}

__all__ = ["ACTION_DIALOGS", "ConfigDialog", "FirmwareDialog", "UserDialog"]
