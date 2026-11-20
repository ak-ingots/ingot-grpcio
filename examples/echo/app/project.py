"""
The project of the echo: an RPC answering by an operation run for the
anonymous caller, another failing by an error its policy encodes, so that
the load measures what ingot-grpcio adds to grpcio, on a call and on a
failure.
"""

import typing as t

import grpc
from grpc import aio

from echo.v1 import echo_pb2_grpc
from echo.v1.echo_pb2 import (
    FailEchoRequest,
    FailEchoResponse,
    SendEchoRequest,
    SendEchoResponse,
)
from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.errors import BaseStaticGrpcErrorPolicy, GrpcErrorsUnit
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServersUnit
from ingot_grpcio.grpc.services import GrpcService, GrpcServicer
from ingots.defaults.operations import (
    BaseOperation,
    CallersProvider,
    OperationMetadata,
    OperationsOwner,
    OperationsUnit,
    PermissionFlags,
    Permissions,
    PermissionsSlot,
)
from ingots.puer import Factory, Slot, Unit, UserError


class EchoFailedError(UserError):
    """The failure the echo is asked for. Create it with :meth:`for_text`."""

    @classmethod
    def for_text(cls, text: str) -> t.Self:
        return cls(f"the echo of {text!r} failed, as asked", text)

    @property
    def text(self) -> str:
        return t.cast(str, self.args[1])

    @t.override
    def __str__(self) -> str:
        return t.cast(str, self.args[0])


class EchoFailedPolicy(BaseStaticGrpcErrorPolicy):
    EXCEPTION = EchoFailedError
    CODE = grpc.StatusCode.FAILED_PRECONDITION
    DOMAIN = "echo.example.com"
    REASON = "ECHO_FAILED"

    @t.override
    def _get_metadata(self, error: Exception) -> dict[str, str]:
        return {"text": t.cast(EchoFailedError, error).text}


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


class EchoUnit(OperationsOwner, Unit):
    class Flags(PermissionFlags):
        CAN_ECHO = 1 << 0

    permissions = PermissionsSlot(Flags)
    op_send = Factory(SendEchoOperation)
    op_fail = Factory(FailEchoOperation)


class EchoCallersProvider(CallersProvider):
    """Anyone may echo."""

    @t.override
    def _get_anonymous_permissions(self) -> Permissions:
        flags = EchoUnit.Flags.CAN_ECHO
        return super()._get_anonymous_permissions() | Permissions({"echo": flags})


class EchoOperationsUnit(OperationsUnit):
    callers = Slot(EchoCallersProvider)


SendContext: t.TypeAlias = aio.ServicerContext[SendEchoRequest, SendEchoResponse]
FailContext: t.TypeAlias = aio.ServicerContext[FailEchoRequest, FailEchoResponse]


class EchoServicer(GrpcServicer, echo_pb2_grpc.EchoServiceServicer):
    project: "EchoProject"

    @t.override
    async def SendEcho(
        self, request: SendEchoRequest, context: SendContext
    ) -> SendEchoResponse:
        send = self.project.echo.op_send
        return SendEchoResponse(
            text=await self.run_operation(send, request.text, context)
        )

    @t.override
    async def FailEcho(
        self, request: FailEchoRequest, context: FailContext
    ) -> FailEchoResponse:
        await self.run_operation(self.project.echo.op_fail, request.text, context)
        return FailEchoResponse()  # never: the operation fails


class EchoGrpcBinding:
    echo = GrpcService(echo_pb2_grpc.EchoServiceStub, EchoServicer)


class EchoGrpcServer(EchoGrpcBinding, DefaultGrpcServer):
    pass


class EchoGrpcErrorsUnit(GrpcErrorsUnit):
    echo_failed = Slot(EchoFailedPolicy)


class EchoGrpcServersUnit(GrpcServersUnit):
    default = Slot(EchoGrpcServer)


class EchoGrpcUnit(GrpcUnit):
    errors = Slot(EchoGrpcErrorsUnit)
    servers = Slot(EchoGrpcServersUnit)


class EchoProject(GrpcProject):
    env_configs_prefix = "APP"
    operations = Slot(EchoOperationsUnit)
    grpc = Slot(EchoGrpcUnit)
    echo = Slot(EchoUnit)
