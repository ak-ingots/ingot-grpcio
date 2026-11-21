"""The operations of the echo: a text answered, or failed as asked."""

__all__ = ("BaseEchoOperation", "FailEchoOperation", "SendEchoOperation")

import typing as t

from ingots.defaults.operations import BaseOperation, OperationMetadata, Permissions

from .errors import EchoFailedError

if t.TYPE_CHECKING:
    from . import EchoUnit


class BaseEchoOperation(BaseOperation[str, str]):
    """An operation of the echo, anyone may run."""

    parent: "EchoUnit"

    @t.override
    def _get_permissions(self) -> Permissions:
        permissions = self.parent.permissions
        return permissions(permissions.flags.CAN_ECHO)


class SendEchoOperation(BaseEchoOperation):
    @t.override
    async def _run(self, parameters: str, metadata: OperationMetadata) -> str:
        return parameters


class FailEchoOperation(BaseEchoOperation):
    @t.override
    async def _run(self, parameters: str, metadata: OperationMetadata) -> str:
        raise EchoFailedError.for_text(parameters)
