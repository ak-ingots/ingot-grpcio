"""The base of the gRPC servers: a component serving services."""

__all__ = ("BaseGrpcServer",)

import logging
import typing as t

from grpc import aio
from ingots.puer import Component

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from ingot_grpcio.grpc.api import GrpcService

logger = logging.getLogger(__name__)


class BaseGrpcServer(Component):
    """
    A gRPC server of grpcio: configured, it listens on its hosts and port and
    serves its services; shut down, it stops accepting and gives the calls
    in progress a grace period. Run it as any server of the project:
    ``components run-forever --component grpc.servers.default``.

    A server takes its settings and services from the hooks, which a
    subclass implements: :meth:`_get_listen_hosts`, :meth:`_get_port`,
    :meth:`_get_max_concurrent_rpcs`, :meth:`_get_shutdown_grace`,
    :meth:`_iter_services`, the services of its binding, and
    :meth:`_iter_interceptors`, which see every call.
    """

    SHUTDOWN_ORDER = 2

    _server: aio.Server
    _addresses: tuple[str, ...] = ()

    @t.final
    @property
    def addresses(self) -> tuple[str, ...]:
        """
        The addresses the server listens on, ``host:port``, once configured:
        with the port the system chose for port 0.
        """
        return self._addresses

    @t.override
    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {', '.join(self._addresses) or '-'}>"

    @t.override
    async def _configure(self) -> None:
        server = aio.server(
            interceptors=list(self._iter_interceptors()),
            maximum_concurrent_rpcs=self._get_max_concurrent_rpcs(),
        )
        services = []
        for service in self._iter_services():
            service.add_to_server(server)
            services.append(service.FULL_NAME)
        port = self._get_port()
        addresses = []
        for host in self._get_listen_hosts():
            bound = server.add_insecure_port(f"{host}:{port}")
            addresses.append(f"{host}:{bound}")
        await server.start()
        self._server, self._addresses = server, tuple(addresses)
        if services:
            logger.info("%r: serving %s", self, ", ".join(services))
        else:
            logger.warning("%r: serving nothing: its binding gives no services", self)

    @t.override
    async def _shut_down(self) -> None:
        grace = self._get_shutdown_grace()
        logger.info("%r: stopping, %s s of grace", self, grace)
        await self._server.stop(grace)
        logger.info("%r: stopped", self)

    def _get_listen_hosts(self) -> tuple[str, ...]:
        """The hosts to listen on: ``("[::]",)`` for every interface."""
        raise NotImplementedError(f"{type(self).__qualname__}._get_listen_hosts")

    def _get_port(self) -> int:
        """The port to listen on, on every host; 0 lets the system choose."""
        raise NotImplementedError(f"{type(self).__qualname__}._get_port")

    def _get_max_concurrent_rpcs(self) -> int | None:
        """The calls served at once, the others refused; ``None``: no limit."""
        raise NotImplementedError(f"{type(self).__qualname__}._get_max_concurrent_rpcs")

    def _get_shutdown_grace(self) -> float:
        """The seconds the calls in progress get to finish at the shutdown."""
        raise NotImplementedError(f"{type(self).__qualname__}._get_shutdown_grace")

    def _iter_services(self) -> "Iterator[GrpcService]":
        """The services to serve: those of the binding of the server."""
        raise NotImplementedError(f"{type(self).__qualname__}._iter_services")

    def _iter_interceptors(self) -> "Iterator[aio.ServerInterceptor]":
        """
        The interceptors of the calls, the outermost first. A subclass adding
        its own yields those of its base first, so that the interceptor of
        the errors encodes theirs too: without it, grpcio sends a client the
        text of an exception, as ``UNKNOWN``.
        """
        raise NotImplementedError(f"{type(self).__qualname__}._iter_interceptors")
