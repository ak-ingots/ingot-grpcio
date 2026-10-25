"""The interceptor encoding the exceptions of the RPCs of a server."""

__all__ = ("ServerGrpcErrorsInterceptor",)

import inspect
import typing as t

import grpc
from grpc import aio
from grpc_status import rpc_status

if t.TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable

    from ingot_grpcio.grpc.errors import ServerGrpcErrorHandler

Behavior: t.TypeAlias = "Callable[..., t.Any]"
Handler: t.TypeAlias = grpc.RpcMethodHandler


class ServerGrpcErrorsInterceptor(aio.ServerInterceptor):
    """
    Handles an exception an RPC raises with the server handler of the errors,
    which logs and encodes it, and aborts the call with its status: every
    kind of RPC, streams included. An abort of the handler of the RPC
    itself passes as it is.
    """

    def __init__(self, handler: "ServerGrpcErrorHandler", is_debug_info: bool) -> None:
        self._handler = handler
        self._is_debug_info = is_debug_info

    @t.override
    async def intercept_service[Request, Response](
        self,
        continuation: "Callable[[grpc.HandlerCallDetails], Awaitable[Handler[Request, Response] | None]]",  # noqa: E501
        handler_call_details: grpc.HandlerCallDetails,
    ) -> "Handler[Request, Response] | None":
        handler = await continuation(handler_call_details)
        if handler is None:
            return None  # an unknown method: grpcio answers UNIMPLEMENTED
        kind = "_".join(
            "stream" if streaming else "unary"
            for streaming in (handler.request_streaming, handler.response_streaming)
        )
        behavior = self._wrap(getattr(handler, kind), handler_call_details.method)
        build = getattr(grpc, f"{kind}_rpc_method_handler")
        return t.cast(
            "Handler[Request, Response]",
            build(
                behavior,
                request_deserializer=handler.request_deserializer,
                response_serializer=handler.response_serializer,
            ),
        )

    def _wrap(self, behavior: Behavior, method: str) -> Behavior:
        if inspect.isasyncgenfunction(behavior):

            async def stream(
                request: t.Any, context: aio.ServicerContext[t.Any, t.Any]
            ) -> "AsyncIterator[t.Any]":
                try:
                    async for response in behavior(request, context):
                        yield response
                except aio.AbortError:
                    raise
                except Exception as error:
                    await self._abort(error, context, method)

            return stream

        async def call(
            request: t.Any, context: aio.ServicerContext[t.Any, t.Any]
        ) -> t.Any:
            try:
                return await behavior(request, context)
            except aio.AbortError:
                raise
            except Exception as error:
                await self._abort(error, context, method)

        return call

    async def _abort(
        self,
        error: Exception,
        context: aio.ServicerContext[t.Any, t.Any],
        method: str,
    ) -> t.NoReturn:
        status = self._handler.handle(error, method, is_debug_info=self._is_debug_info)
        await context.abort_with_status(rpc_status.to_status(status))
        raise AssertionError("abort_with_status() returned")  # pragma: no cover
