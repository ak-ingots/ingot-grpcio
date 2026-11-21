"""
The echo, the domain of the application, of no transport: an operation
answering, another failing by an error, anyone may run them; its contract
of gRPC, ``echo.v1``, next to it.
"""

__all__ = ("EchoFailedError", "EchoUnit", "FailEchoOperation", "SendEchoOperation")

from ingots.defaults.operations import OperationsOwner, PermissionFlags
from ingots.defaults.operations import PermissionsSlot
from ingots.puer import Factory, Unit

from .errors import EchoFailedError
from .operations import FailEchoOperation, SendEchoOperation


class EchoUnit(OperationsOwner, Unit):
    class Flags(PermissionFlags):
        CAN_ECHO = 1 << 0

    permissions = PermissionsSlot(Flags)
    op_send = Factory(SendEchoOperation)
    op_fail = Factory(FailEchoOperation)
