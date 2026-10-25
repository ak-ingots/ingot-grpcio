"""The interceptor decoding the failed calls of a client."""

__all__ = ("ClientGrpcErrorsInterceptor",)

import typing as t

from grpc import aio

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable
    from collections.abc import Iterable

    from ingot_grpcio.grpc.errors import ClientGrpcErrorHandler

Requests: t.TypeAlias = "AsyncIterable[t.Any] | Iterable[t.Any]"


class ClientGrpcErrorsInterceptor(
    aio.UnaryUnaryClientInterceptor,
    aio.UnaryStreamClientInterceptor,
    aio.StreamUnaryClientInterceptor,
    aio.StreamStreamClientInterceptor,
):
    """
    Raises a failed call as the :class:`~ingot_grpcio.grpc.errors.GrpcError`
    the client handler of the errors decodes, the ``AioRpcError`` of grpcio
    as its cause: every kind of RPC, at the ``await`` of a unary response or
    at the failing read of a stream. The call stays a call: its metadata,
    code and ``cancel()`` are there, and so is ``write()`` of a stream.
    """

    def __init__(self, handler: "ClientGrpcErrorHandler") -> None:
        self._handler = handler

    @t.override
    async def intercept_unary_unary(
        self,
        continuation: "Callable[[aio.ClientCallDetails, t.Any], Awaitable[aio.UnaryUnaryCall[t.Any, t.Any]]]",  # noqa: E501
        client_call_details: aio.ClientCallDetails,
        request: t.Any,
    ) -> "aio.UnaryUnaryCall[t.Any, t.Any]":
        call = await continuation(client_call_details, request)
        await self._wait(call, client_call_details)
        return call

    @t.override
    async def intercept_unary_stream(
        self,
        continuation: "Callable[[aio.ClientCallDetails, t.Any], Awaitable[aio.UnaryStreamCall[t.Any, t.Any]]]",  # noqa: E501
        client_call_details: aio.ClientCallDetails,
        request: t.Any,
    ) -> "AsyncIterator[t.Any]":
        call = await continuation(client_call_details, request)
        return self._iter(call, client_call_details)

    @t.override
    async def intercept_stream_unary(
        self,
        continuation: "Callable[[aio.ClientCallDetails, Requests], Awaitable[aio.StreamUnaryCall[t.Any, t.Any]]]",  # noqa: E501
        client_call_details: aio.ClientCallDetails,
        request_iterator: Requests,
    ) -> "aio.StreamUnaryCall[t.Any, t.Any]":
        call = await continuation(client_call_details, request_iterator)
        await self._wait(call, client_call_details)
        return call

    @t.override
    async def intercept_stream_stream(
        self,
        continuation: "Callable[[aio.ClientCallDetails, Requests], Awaitable[aio.StreamStreamCall[t.Any, t.Any]]]",  # noqa: E501
        client_call_details: aio.ClientCallDetails,
        request_iterator: Requests,
    ) -> "AsyncIterator[t.Any]":
        call = await continuation(client_call_details, request_iterator)
        return self._iter(call, client_call_details)

    async def _wait(
        self,
        call: "aio.UnaryUnaryCall[t.Any, t.Any] | aio.StreamUnaryCall[t.Any, t.Any]",
        details: aio.ClientCallDetails,
    ) -> None:
        # the call is returned, not its response: the caller keeps its metadata
        try:
            await call
        except aio.AioRpcError as error:
            raise self._handler.handle(error, get_method(details)) from error

    async def _iter(
        self,
        call: "aio.UnaryStreamCall[t.Any, t.Any] | aio.StreamStreamCall[t.Any, t.Any]",
        details: aio.ClientCallDetails,
    ) -> "AsyncIterator[t.Any]":
        # grpcio wraps the iterator in a call of the call it is given
        try:
            async for response in call:
                yield response
        except aio.AioRpcError as error:
            raise self._handler.handle(error, get_method(details)) from error


def get_method(details: aio.ClientCallDetails) -> str:
    """Internal: the method of a call, which grpcio gives in bytes."""
    method: str | bytes = details.method
    return method.decode() if isinstance(method, bytes) else method
