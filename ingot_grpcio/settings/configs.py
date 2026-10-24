"""The configs of the addon, named ``GRPC_*``."""

__all__ = ("GrpcConfigs",)

import logging

from ingots.defaults.settings.configs import Configs, LogLevelConfig


class GrpcConfigs(Configs):
    """The configs of the defaults with those of grpcio."""

    GRPC_LOGGING_LEVEL = LogLevelConfig(logging.INFO)
