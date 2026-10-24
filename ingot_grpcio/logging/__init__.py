"""The logging unit of the defaults with the logger of the addon."""

__all__ = ("GrpcLogging",)

import typing as t

from ingots.defaults.logging import Logging

if t.TYPE_CHECKING:
    from ..project import GrpcProject


class GrpcLogging(Logging):
    """
    The logging unit, with the logger of the addon, ``ingot_grpcio``, at
    ``GRPC_LOGGING_LEVEL``.
    """

    project: "GrpcProject"

    @t.override
    def build_loggers(self) -> dict[str, dict[str, t.Any]]:
        level = self.project.settings.configs.GRPC_LOGGING_LEVEL
        addon = {"level": level, "handlers": ["default"], "propagate": False}
        return {**super().build_loggers(), "ingot_grpcio": addon}
