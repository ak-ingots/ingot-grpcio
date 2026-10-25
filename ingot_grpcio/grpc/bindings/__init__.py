"""The bindings: which services each server of the project serves."""

__all__ = ("AutoGrpcBinding", "BaseGrpcBinding", "GrpcBindings")

from ingots.puer import Slot, Unit

from .auto import AutoGrpcBinding
from .base import BaseGrpcBinding


class GrpcBindings(Unit):
    """
    The bindings of the servers, each under the name of its server:
    :attr:`default` for ``grpc.servers.default``. Another server takes a
    binding of its own here, under its name.
    """

    default = Slot(AutoGrpcBinding)
