"""Shim to expose Villa from generators.villas

This module is present because some modules import `devices.villa`.
It re-exports `Villa` and `VillaData` from `generators.villas`.
"""

from generators.villas import Villa, VillaData

__all__ = ["Villa", "VillaData"]
