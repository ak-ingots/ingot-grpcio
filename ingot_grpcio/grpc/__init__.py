"""The gRPC unit: the errors, the servers and the clients of the project."""

__all__ = ("GrpcUnit",)

from ingots.puer import Slot, Unit

from .clients import GrpcClients
from .errors import GrpcErrors
from .servers import GrpcServers


class GrpcUnit(Unit):
    """
    gRPC in the project: :attr:`errors`, the policies of the exceptions of
    the business logic; :attr:`servers` and :attr:`clients`, the servers
    and the clients, each a component. The services are attributes of the
    servers and clients, from the bindings they extend
    (:class:`~ingot_grpcio.grpc.services.GrpcService`); an application
    declares its own in subclasses of the units::

        class AppGrpcServers(GrpcServers):
            default = Slot(AppGrpcServer)
    """

    errors = Slot(GrpcErrors)
    servers = Slot(GrpcServers)
    clients = Slot(GrpcClients)
