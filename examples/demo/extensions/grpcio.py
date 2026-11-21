"""
gRPC in the application: the servicer of the echo, running its operations,
the server serving it, the policy encoding the failure of the echo.
"""

__all__ = ("EchoGrpcUnit", "EchoServicer")

import typing as t

import grpc
from grpc import aio

from echo import EchoFailedError
from echo.v1 import echo_pb2_grpc
from echo.v1.echo_pb2 import (
    FailEchoRequest,
    FailEchoResponse,
    SendEchoRequest,
    SendEchoResponse,
)
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.errors import BaseStaticGrpcErrorPolicy, GrpcErrorsUnit
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServersUnit
from ingot_grpcio.grpc.services import GrpcService, GrpcServicer
from ingots.puer import Slot

if t.TYPE_CHECKING:
    from project import EchoProject


class EchoFailedPolicy(BaseStaticGrpcErrorPolicy):
    EXCEPTION = EchoFailedError
    CODE = grpc.StatusCode.FAILED_PRECONDITION
    DOMAIN = "echo.example.com"
    REASON = "ECHO_FAILED"

    @t.override
    def _get_metadata(self, error: Exception) -> dict[str, str]:
        return {"text": t.cast(EchoFailedError, error).text}


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
