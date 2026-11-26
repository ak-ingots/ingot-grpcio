"""The gRPC unit: the errors, the servers and the clients of the project."""

__all__ = ("GrpcCliUnit", "GrpcCommandsUnit", "GrpcUnit")

from ingots.puer import Slot, Unit

from .clients import GrpcClientsUnit
from .commands import GrpcCliUnit, GrpcCommandsUnit
from .errors import GrpcErrorsUnit
from .servers import GrpcServersUnit


class GrpcUnit(Unit):
    """
    gRPC in the project: :attr:`errors`, the policies of the exceptions of
    the business logic; :attr:`servers` and :attr:`clients`, the servers
    and the clients, each a component. The services are attributes of the
    servers and clients, from the bindings they extend
    (:class:`~ingot_grpcio.grpc.services.GrpcService`); an application
    declares its own in subclasses of the units::

        class AppGrpcServersUnit(GrpcServersUnit):
            default = Slot(AppGrpcServer)

    On the command line, ``grpc export`` of :class:`GrpcCliUnit` writes
    the services of the servers for client SDKs.
    """

    errors = Slot(GrpcErrorsUnit)
    servers = Slot(GrpcServersUnit)
    clients = Slot(GrpcClientsUnit)
