"""The project of the addon: what an application inherits from."""

__all__ = ("GrpcProject",)

from ingots.defaults import Project
from ingots.puer import Slot

from .logging import GrpcLogging
from .settings import GrpcSettings


class GrpcProject(Project):
    """
    The project of the defaults with the addon's :class:`GrpcSettings` and
    :class:`GrpcLogging`. An application inherits from it and sets its own
    ``env_configs_prefix``; the addon run on its own (``python -m ingot_grpcio``)
    keeps the prefix of the defaults, ``INGOT``.
    """

    settings = Slot(GrpcSettings)
    logging = Slot(GrpcLogging)
