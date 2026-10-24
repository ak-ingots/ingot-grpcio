"""The settings unit of the defaults with the configs of the addon."""

__all__ = ("GrpcSettings",)

from ingots.defaults.settings import Settings
from ingots.puer import Slot

from .configs import GrpcConfigs


class GrpcSettings(Settings):
    """The settings unit, with the addon's :class:`GrpcConfigs`."""

    configs = Slot(GrpcConfigs)
