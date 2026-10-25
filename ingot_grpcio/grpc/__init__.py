"""The gRPC unit: the API of the project, its bindings and its servers."""

__all__ = ("GrpcUnit",)

from ingots.puer import Slot, Unit

from .api import GrpcApi
from .bindings import GrpcBindings
from .errors import GrpcErrors
from .servers import GrpcServers


class GrpcUnit(Unit):
    """
    gRPC in the project: :attr:`api`, the registry of the services;
    :attr:`bindings`, which of them each server serves; :attr:`errors`, the
    policies of the exceptions of the business logic; :attr:`servers`, the
    servers, each a component. An application adds its services to a
    subclass of :class:`GrpcApi` and declares ``api = Slot(AppGrpcApi)`` in
    a subclass of this unit.
    """

    api = Slot(GrpcApi)
    bindings = Slot(GrpcBindings)
    errors = Slot(GrpcErrors)
    servers = Slot(GrpcServers)
