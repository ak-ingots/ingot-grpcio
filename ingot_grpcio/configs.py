"""The configs of the addon, named ``GRPC_*``."""

__all__ = ("Configs",)

import logging

from ingots.defaults.settings.configs import Configs as BaseConfigs
from ingots.defaults.settings.configs import LogLevelConfig


class Configs(BaseConfigs):
    """The configs of the defaults with those of grpcio."""

    GRPC_LOGGING_LEVEL = LogLevelConfig(logging.INFO)
