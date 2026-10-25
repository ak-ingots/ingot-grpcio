"""The base of the bindings: which services a server serves."""

__all__ = ("BaseGrpcBinding",)

import typing as t

from ingots.puer import Entity

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from ingot_grpcio.grpc.api import GrpcService


class BaseGrpcBinding(Entity):
    """
    The services of one server: the policy of what it exposes, kept apart
    from the server, which is where they are served. A server and its
    binding take the same name: ``grpc.servers.default`` serves
    ``grpc.bindings.default``, and a client of the server finds its
    services there too.

    A subclass chooses the services in :meth:`_iter_services`.
    """

    @t.override
    def __repr__(self) -> str:
        return f"<{type(self).__qualname__}>"

    @t.final
    def iter_services(self) -> "Iterator[GrpcService]":
        """
        The services to serve, each once and with an implementation.

        :raises TypeError: a service without a servicer, or one given twice.
        """
        seen: set[str] = set()
        for service in self._iter_services():
            full_name = service.FULL_NAME
            if not hasattr(service, "SERVICER"):
                raise TypeError(f"{self!r}: {service!r} has no SERVICER to serve")
            if full_name in seen:
                raise TypeError(f"{self!r}: {full_name!r} is given twice")
            seen.add(full_name)
            yield service

    def _iter_services(self) -> "Iterator[GrpcService]":
        """The services the server serves."""
        raise NotImplementedError(f"{type(self).__qualname__}._iter_services")
