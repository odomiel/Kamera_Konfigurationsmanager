"""Front-view action dialogs (one per former Kameraeinstellungen tab)."""

from kkm.core import Capability
from .config_dialog import ConfigDialog
from .firmware_dialog import FirmwareDialog
from .user_dialog import UserDialog
from .onvif_dialog import OnvifDialog

# Maps a Capability to the dialog that handles it. The main window looks the
# action up here; the remaining action (IP) registers the same way.
ACTION_DIALOGS = {
    Capability.CONFIG: ConfigDialog,
    Capability.FIRMWARE: FirmwareDialog,
    Capability.USERS: UserDialog,
    Capability.ONVIF_USERS: OnvifDialog,
}

__all__ = ["ACTION_DIALOGS", "ConfigDialog", "FirmwareDialog", "UserDialog",
           "OnvifDialog"]
