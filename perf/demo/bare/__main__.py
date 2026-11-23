"""``python -m bare [PORT]``: the echo on grpcio alone, until stopped."""

import asyncio
import sys
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


class BareEchoServicer(echo_pb2_grpc.EchoServiceServicer):
    @t.override
    async def SendEcho(
        self,
        request: SendEchoRequest,
        context: aio.ServicerContext[SendEchoRequest, SendEchoResponse],
    ) -> SendEchoResponse:
        return SendEchoResponse(text=request.text)

    @t.override
    async def FailEcho(
        self,
        request: FailEchoRequest,
        context: aio.ServicerContext[FailEchoRequest, FailEchoResponse],
    ) -> FailEchoResponse:
        await context.abort(
            grpc.StatusCode.FAILED_PRECONDITION,
            f"the echo of {request.text!r} failed, as asked",
        )


async def serve(port: int) -> None:
    server = aio.server()
    echo_pb2_grpc.add_EchoServiceServicer_to_server(BareEchoServicer(), server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    await server.wait_for_termination()


if __name__ == "__main__":
    asyncio.run(serve(int(sys.argv[1]) if len(sys.argv) > 1 else 50051))
