"""The project of the addon: what an application inherits from."""

__all__ = ("GrpcProject",)

from ingots.defaults import Project
from ingots.puer import Slot

from .cli import GrpcCliUnit
from .grpc import GrpcUnit
from .logging import GrpcLoggingUnit
from .settings import GrpcSettingsUnit


class GrpcProject(Project):
    """
    The project of the defaults with the addon's :class:`GrpcSettingsUnit`,
    :class:`GrpcLoggingUnit`, gRPC, :class:`GrpcUnit`, and its commands,
    :class:`GrpcCliUnit`. An application inherits
    from it and sets its own ``env_configs_prefix``; the addon run on its own
    (``python -m ingot_grpcio``) keeps the prefix of the defaults, ``INGOT``.
    """

    settings = Slot(GrpcSettingsUnit)
    logging = Slot(GrpcLoggingUnit)
    grpc = Slot(GrpcUnit)
    cli = Slot(GrpcCliUnit)
