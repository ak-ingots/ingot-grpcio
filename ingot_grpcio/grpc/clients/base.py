"""The base of the gRPC clients: a component calling services."""

__all__ = ("BaseGrpcClient",)

import logging
import typing as t

from grpc import aio
from ingots.puer import Component

from ingot_grpcio.grpc.services import GrpcService, GrpcServicesOwner

if t.TYPE_CHECKING:
    from collections.abc import Iterator

logger = logging.getLogger(__name__)


class BaseGrpcClient(GrpcServicesOwner, Component):
    """
    A gRPC client of grpcio: configured, it opens a channel to its target
    and creates the stubs of the services of the bindings it extends; shut
    down, it closes the channel. Awaited, it is ready to call::

        client = await self.project.grpc.clients.default
        reply = await client.echo.Say(demo_pb2.EchoMessage(text="ingots"))

    ``client.echo`` is the stub, typed as the async stub that mypy-protobuf
    generates. A client takes its settings from the hooks, which a subclass
    implements: :meth:`_get_target` and :meth:`_iter_interceptors`, which
    see every call.
    An interceptor of several kinds of RPCs is one class: grpcio takes it
    for the first of them only, so the client gives grpcio a part of it for
    each. It shuts down before the servers, the calls first.
    """

    SHUTDOWN_ORDER = 1

    _target: str
    _channel: aio.Channel
    _stubs: dict[str, object]

    @t.override
    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {getattr(self, '_target', '-')}>"

    @t.override
    async def _configure(self) -> None:
        target = self._get_target()
        interceptors = [
            part
            for interceptor in self._iter_interceptors()
            for part in split_interceptor(interceptor)
        ]
        channel = aio.insecure_channel(target, interceptors=interceptors)
        services = list(self.grpc_services_iter())
        self._target, self._channel = target, channel
        self._stubs = {
            service.name: service.build_stub(channel) for service in services
        }
        if services:
            names = ", ".join(service.full_name for service in services)
            logger.info("%r: calling %s", self, names)
        else:
            logger.warning("%r: calling nothing: it extends no binding", self)

    @t.override
    async def _shut_down(self) -> None:
        await self._channel.close()
        logger.info("%r: closed", self)

    @t.override
    def _grpc_services_get(self, service: GrpcService[t.Any, t.Any]) -> object:
        try:
            stubs = self._stubs
        except AttributeError:
            raise RuntimeError(
                f"{self!r} is not configured: await it before its stubs"
            ) from None
        return stubs[service.name]

    def _get_target(self) -> str:
        """The server to call, ``host:port``, or any target grpcio takes."""
        raise NotImplementedError(f"{type(self).__qualname__}._get_target")

    def _iter_interceptors(self) -> "Iterator[aio.ClientInterceptor]":
        """
        The interceptors of the calls, the outermost first. A subclass adding
        its own yields those of its base first, so that the interceptor of
        the errors decodes the failures of theirs too.
        """
        raise NotImplementedError(f"{type(self).__qualname__}._iter_interceptors")


# the kinds of the interceptors of grpcio, each with its method
KINDS: t.Final = (
    (aio.UnaryUnaryClientInterceptor, "intercept_unary_unary"),
    (aio.UnaryStreamClientInterceptor, "intercept_unary_stream"),
    (aio.StreamUnaryClientInterceptor, "intercept_stream_unary"),
    (aio.StreamStreamClientInterceptor, "intercept_stream_stream"),
)


def split_interceptor(
    interceptor: aio.ClientInterceptor,
) -> "Iterator[aio.ClientInterceptor]":
    """
    Internal: an interceptor of one kind of RPCs as it is, one of several
    kinds as a part for each, calling its method of the kind. A channel of
    grpcio sorts its interceptors by ``isinstance``, ``elif``: one of
    several kinds would intercept the first of them only.
    """
    kinds = [(base, name) for base, name in KINDS if isinstance(interceptor, base)]
    if len(kinds) < 2:
        yield interceptor
        return
    for base, name in kinds:
        part_cls = type(
            f"{type(interceptor).__qualname__}[{name}]",
            (base,),
            {name: staticmethod(getattr(interceptor, name))},
        )
        yield t.cast("aio.ClientInterceptor", part_cls())
