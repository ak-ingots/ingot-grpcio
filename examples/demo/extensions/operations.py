"""The operations of the project: who may run what, anyone the echo."""

__all__ = ("EchoCallersProvider", "EchoOperationsUnit")

import typing as t

from ingots.defaults.operations import CallersProvider, OperationsUnit, Permissions
from ingots.puer import Slot

from echo import EchoUnit


class EchoCallersProvider(CallersProvider):
    """Anyone may echo."""

    @t.override
    def _get_anonymous_permissions(self) -> Permissions:
        flags = EchoUnit.Flags.CAN_ECHO
        return super()._get_anonymous_permissions() | Permissions({"echo": flags})


class EchoOperationsUnit(OperationsUnit):
    callers = Slot(EchoCallersProvider)
