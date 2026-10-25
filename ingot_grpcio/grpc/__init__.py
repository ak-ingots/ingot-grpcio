"""The gRPC unit: the API of the project, its bindings and its servers."""

__all__ = ("GrpcUnit",)

from ingots.puer import Slot, Unit

from .api import GrpcApi
from .bindings import GrpcBindings
from .servers import GrpcServers


class GrpcUnit(Unit):
    """
    gRPC in the project: :attr:`api`, the registry of the services;
    :attr:`bindings`, which of them each server serves; :attr:`servers`,
    the servers, each a component. An application adds its services to a
    subclass of :class:`GrpcApi` and declares ``api = Slot(AppGrpcApi)`` in
    a subclass of this unit.
    """

    api = Slot(GrpcApi)
    bindings = Slot(GrpcBindings)
    servers = Slot(GrpcServers)
