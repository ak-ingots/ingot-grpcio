"""
The command line of the addon, the domain of its commands, its modules as
the tree goes: ``grpc.py`` the commands of ``grpc``.
"""

__all__ = ("GrpcCliUnit",)

from ingots.defaults.cli import CliUnit
from ingots.puer import Slot

from .grpc import GrpcCommandsUnit


class GrpcCliUnit(CliUnit):
    """
    The command line of the defaults and ``grpc``; an application of other
    addons with commands joins it with theirs.
    """

    grpc = Slot(GrpcCommandsUnit)
