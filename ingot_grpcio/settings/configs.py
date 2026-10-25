"""The configs of the addon, named ``GRPC_*``."""

__all__ = ("GrpcConfigs",)

import logging

from ingots.defaults.settings.configs import (
    BoolConfig,
    Configs,
    FloatConfig,
    IntConfig,
    LogLevelConfig,
    StrConfig,
)


class GrpcConfigs(Configs):
    """
    The configs of the defaults with those of grpcio. ``GRPC_DEFAULT_*`` are
    the configs of the default server: another server takes configs of its
    own, ``GRPC_<NAME>_*``.
    """

    GRPC_LOGGING_LEVEL = LogLevelConfig(logging.INFO)

    # the default server
    GRPC_DEFAULT_LISTEN_HOST = StrConfig("[::]")
    GRPC_DEFAULT_PORT = IntConfig(50051)
    GRPC_DEFAULT_MAX_CONCURRENT_RPCS = IntConfig(100)  # 0: no limit
    GRPC_DEFAULT_SHUTDOWN_GRACE = FloatConfig(30.0)  # seconds
    GRPC_DEFAULT_IS_SEND_DEBUG_INFO = BoolConfig(False)  # tracebacks to clients
