"""The settings unit of the defaults with the configs of the addon."""

__all__ = ("GrpcSettingsUnit",)

from ingots.defaults.settings import SettingsUnit
from ingots.puer import Slot

from .configs import GrpcConfigs


class GrpcSettingsUnit(SettingsUnit):
    """The settings unit, with the addon's :class:`GrpcConfigs`."""

    configs = Slot(GrpcConfigs)
