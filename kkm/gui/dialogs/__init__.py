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

"""Front-view action dialogs (one per former Kameraeinstellungen tab)."""

from kkm.core import Capability
from .config_dialog import ConfigDialog
from .firmware_dialog import FirmwareDialog
from .user_dialog import UserDialog
from .onvif_dialog import OnvifDialog
from .ip_dialog import IpDialog

# Maps a Capability to the dialog that handles it. The main window looks the
# action up here. All five front-view actions are now wired.
ACTION_DIALOGS = {
    Capability.CONFIG: ConfigDialog,
    Capability.FIRMWARE: FirmwareDialog,
    Capability.USERS: UserDialog,
    Capability.ONVIF_USERS: OnvifDialog,
    Capability.SET_IP: IpDialog,
}

__all__ = ["ACTION_DIALOGS", "ConfigDialog", "FirmwareDialog", "UserDialog",
           "OnvifDialog", "IpDialog"]
