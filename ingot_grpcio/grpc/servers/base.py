"""The base of the gRPC servers: a component serving services."""

__all__ = ("BaseGrpcServer",)

import logging
import typing as t

from grpc import aio
from ingots.puer import Component

from ingot_grpcio.grpc.services import GrpcService, GrpcServicer, GrpcServicesOwner

if t.TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class BaseGrpcServer(GrpcServicesOwner, Component):
    """
    A gRPC server of grpcio: configured, it listens on its hosts and port and
    serves its services; shut down, it stops accepting and gives the calls
    in progress a grace period. Run it as any server of the project:
    ``components run-forever --component grpc.servers.default``.

    A server serves the services of the bindings it extends, each by its
    servicer: ``server.echo``, created once with the project. It takes its
    settings from the hooks, which a subclass implements:
    :meth:`_get_listen_hosts`, :meth:`_get_port`,
    :meth:`_get_max_concurrent_rpcs`, :meth:`_get_shutdown_grace` and
    :meth:`_iter_interceptors`, which see every call.

    :raises TypeError: a service of the class has no servicer.
    """

    SHUTDOWN_ORDER = 2

    _server: aio.Server
    _addresses: tuple[str, ...] = ()
    _servicers: dict[str, GrpcServicer]

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        check_servicers(cls)

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
        for service in self.grpc_services_iter():
            service.add_to_server(self._grpc_services_get(service), server)
            services.append(service.full_name)
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
            logger.warning("%r: serving nothing: it extends no binding", self)

    @t.override
    async def _shut_down(self) -> None:
        grace = self._get_shutdown_grace()
        logger.info("%r: stopping, %s s of grace", self, grace)
        await self._server.stop(grace)
        logger.info("%r: stopped", self)

    @t.override
    def _grpc_services_get(self, service: GrpcService[t.Any, t.Any]) -> GrpcServicer:
        try:
            servicers = self._servicers
        except AttributeError:
            servicers = self._servicers = {}
        try:
            return servicers[service.name]
        except KeyError:
            servicer: GrpcServicer = service.build_servicer(self.project)
            servicers[service.name] = servicer
            return servicer

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

    def _iter_interceptors(self) -> "Iterator[aio.ServerInterceptor]":
        """
        The interceptors of the calls, the outermost first. A subclass adding
        its own yields those of its base first, so that the interceptor of
        the errors encodes theirs too: without it, grpcio sends a client the
        text of an exception, as ``UNKNOWN``.
        """
        raise NotImplementedError(f"{type(self).__qualname__}._iter_interceptors")


def check_servicers(cls: type[BaseGrpcServer]) -> None:
    """Internal, run when the class is created: a server serves no contract."""
    for service in cls.grpc_services_iter():
        if service.servicer_cls is None:
            raise TypeError(
                f"{cls.__qualname__}.{service.name}: {service!r} has no servicer "
                f"to serve"
            )
