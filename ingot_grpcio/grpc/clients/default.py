"""The default gRPC client of the project: of its default server."""

__all__ = ("DefaultGrpcClient",)

import typing as t

from .base import BaseGrpcClient
from .interceptor import ClientGrpcErrorsInterceptor

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from grpc import aio

    from ingot_grpcio.project import GrpcProject


class DefaultGrpcClient(BaseGrpcClient):
    """
    The client of the default server: it calls ``GRPC_DEFAULT_HOST`` on
    ``GRPC_DEFAULT_PORT``, the port the server listens on. It calls nothing
    by itself: an application extends it with the bindings of the server,
    ``class AppGrpcClient(AppGrpcBinding, DefaultGrpcClient)``. It raises
    the failed calls as a :class:`~ingot_grpcio.grpc.errors.GrpcError` with
    ``grpc.errors.client_handler``.
    """

    project: "GrpcProject"

    @t.override
    def _get_target(self) -> str:
        configs = self.project.settings.configs
        return f"{configs.GRPC_DEFAULT_HOST}:{configs.GRPC_DEFAULT_PORT}"

    @t.override
    def _iter_interceptors(self) -> "Iterator[aio.ClientInterceptor]":
        yield ClientGrpcErrorsInterceptor(self.project.grpc.errors.client_handler)
