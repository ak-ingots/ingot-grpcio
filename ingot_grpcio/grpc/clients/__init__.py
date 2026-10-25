"""The clients: the gRPC clients of the project, each a component."""

__all__ = (
    "BaseGrpcClient",
    "ClientGrpcErrorsInterceptor",
    "DefaultGrpcClient",
    "GrpcClients",
)

from ingots.puer import Slot, Unit

from .base import BaseGrpcClient
from .default import DefaultGrpcClient
from .interceptor import ClientGrpcErrorsInterceptor


class GrpcClients(Unit):
    """
    The gRPC clients of the project: :attr:`default`, of the default
    server, for a start. A client of another server, of the project or
    written in anything, extends :class:`BaseGrpcClient` with configs and
    bindings of its own.
    """

    default = Slot(DefaultGrpcClient)
