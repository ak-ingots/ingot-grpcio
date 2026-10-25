"""The default gRPC server of the project."""

__all__ = ("DefaultGrpcServer",)

import typing as t

from .base import BaseGrpcServer
from .interceptor import ServerGrpcErrorsInterceptor

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from grpc import aio

    from ingot_grpcio.project import GrpcProject


class DefaultGrpcServer(BaseGrpcServer):
    """
    The server of the configs ``GRPC_DEFAULT_*``. It serves nothing by
    itself: an application extends it with its bindings,
    ``class AppGrpcServer(AppGrpcBinding, DefaultGrpcServer)``. It logs and
    encodes the exceptions of the RPCs with ``grpc.errors.server_handler``.
    """

    project: "GrpcProject"

    @t.override
    def _get_listen_hosts(self) -> tuple[str, ...]:
        return (self.project.settings.configs.GRPC_DEFAULT_LISTEN_HOST,)

    @t.override
    def _get_port(self) -> int:
        return self.project.settings.configs.GRPC_DEFAULT_PORT

    @t.override
    def _get_max_concurrent_rpcs(self) -> int | None:
        return self.project.settings.configs.GRPC_DEFAULT_MAX_CONCURRENT_RPCS or None

    @t.override
    def _get_shutdown_grace(self) -> float:
        return self.project.settings.configs.GRPC_DEFAULT_SHUTDOWN_GRACE

    @t.override
    def _get_is_reflection(self) -> bool:
        return self.project.settings.configs.GRPC_DEFAULT_IS_REFLECTION

    @t.override
    def _iter_interceptors(self) -> "Iterator[aio.ServerInterceptor]":
        configs = self.project.settings.configs
        yield ServerGrpcErrorsInterceptor(
            self.project.grpc.errors.server_handler,
            configs.GRPC_DEFAULT_IS_SEND_DEBUG_INFO,
        )
