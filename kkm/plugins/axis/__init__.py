"""Axis vendor plugin package.

``vapix.py`` and ``discovery.py`` are copied from the Axis_Kamera_Discovery tool
and maintained here independently (per the project decision to copy, not share).
"""

from .plugin import AxisPlugin

__all__ = ["AxisPlugin"]
