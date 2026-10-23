"""The settings of the defaults with the configs of the addon."""

__all__ = ("Settings",)

from ingots.defaults.settings import Settings as BaseSettings
from ingots.puer import Slot

from .configs import Configs


class Settings(BaseSettings):
    """The settings unit, with the addon's :class:`Configs`."""

    configs = Slot(Configs)
