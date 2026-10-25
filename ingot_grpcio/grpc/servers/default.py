"""The default gRPC server of the project."""

__all__ = ("DefaultGrpcServer",)

import typing as t

from .base import BaseGrpcServer

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from ingot_grpcio.grpc.api import GrpcService
    from ingot_grpcio.project import GrpcProject


class DefaultGrpcServer(BaseGrpcServer):
    """
    The server of the configs ``GRPC_DEFAULT_*``, serving the services of
    ``grpc.bindings.default``: by default, every service of the API.
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
    def _iter_services(self) -> "Iterator[GrpcService]":
        return self.project.grpc.bindings.default.iter_services()
