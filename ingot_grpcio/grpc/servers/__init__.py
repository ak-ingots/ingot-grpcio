"""The servers: the gRPC servers of the project, each a component."""

__all__ = (
    "BaseGrpcServer",
    "DefaultGrpcServer",
    "GrpcServers",
    "ServerGrpcErrorsInterceptor",
)

from ingots.puer import Slot, Unit

from .base import BaseGrpcServer
from .default import DefaultGrpcServer
from .interceptor import ServerGrpcErrorsInterceptor


class GrpcServers(Unit):
    """
    The gRPC servers of the project: :attr:`default` for a start. An
    application with more servers in one process adds them in a subclass,
    each a subclass of :class:`BaseGrpcServer` with configs and bindings of
    its own.
    """

    default = Slot(DefaultGrpcServer)
