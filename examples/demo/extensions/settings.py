"""The settings of the application: the configs of the addon and its own."""

__all__ = ("EchoConfigs", "EchoSettingsUnit")

from ingot_grpcio.settings import GrpcSettingsUnit
from ingot_grpcio.settings.configs import GrpcConfigs
from ingots.puer import Slot


class EchoConfigs(GrpcConfigs):
    """The configs of the application, beside those of the addon."""


class EchoSettingsUnit(GrpcSettingsUnit):
    configs = Slot(EchoConfigs)
