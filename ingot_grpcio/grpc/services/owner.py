"""The owner of services: a server serving them or a client calling them."""

__all__ = ("GrpcServicesOwner",)

import typing as t

from .service import GrpcService

if t.TYPE_CHECKING:
    from collections.abc import Iterator


class GrpcServicesOwner:
    """
    A class with services as attributes, from the bindings it extends: a
    server serving them, a client calling them. Each subclass decides what
    an attribute gives, a servicer or a stub, in :meth:`_grpc_services_get`.

    A subclass replacing a service keeps its contract and refines its
    servicer, as a slot does: ``echo = GrpcService(EchoStub, LoudEcho)``
    replaces ``GrpcService(EchoStub, Echo)`` only if ``LoudEcho`` extends
    ``Echo``.

    :raises TypeError: a replaced service breaks its contract or drops its
        servicer, or two attributes give the same service.
    """

    _grpc_services: t.ClassVar[dict[str, GrpcService[t.Any, t.Any]]] = {}

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        index_services(cls)

    @t.final
    @classmethod
    def grpc_services_iter(cls) -> "Iterator[GrpcService[t.Any, t.Any]]":
        """
        The services of the class, in the order of its bases: ``class
        AppGrpcServer(EchoBinding, PingBinding, ...)`` those of
        ``EchoBinding`` first.
        """
        return iter(cls._grpc_services.values())

    def _grpc_services_get(self, service: GrpcService[t.Any, t.Any]) -> object:
        """What the attribute of a service gives: a servicer, a stub."""
        raise NotImplementedError(f"{type(self).__qualname__}._grpc_services_get")


def index_services(cls: type[GrpcServicesOwner]) -> None:
    """
    Internal, run when the class is created: the services of the class by
    attribute, each replacing those of its bases by the rule of the class.
    """
    services: dict[str, GrpcService[t.Any, t.Any]] = {}
    hidden: set[str] = set()  # names another attribute takes first
    for klass in cls.__mro__:
        for name, value in vars(klass).items():
            if name in services:
                if isinstance(value, GrpcService):
                    check_replacement(cls, value, services[name])
            elif isinstance(value, GrpcService) and name not in hidden:
                services[name] = value
            else:
                hidden.add(name)
    by_full_name: dict[str, str] = {}
    for name, service in services.items():
        owner = by_full_name.setdefault(service.full_name, name)
        if owner != name:
            raise TypeError(
                f"{cls.__qualname__}: {service.full_name!r} is in both {owner} "
                f"and {name}"
            )
    cls._grpc_services = services


def check_replacement(
    cls: type,
    base: GrpcService[t.Any, t.Any],
    service: GrpcService[t.Any, t.Any],
) -> None:
    """Internal: a service replacing another keeps and refines it."""
    where = f"{cls.__qualname__}.{service.name}"
    if service.full_name != base.full_name:
        raise TypeError(f"{where}: {service!r} replaces another service, {base!r}")
    if base.servicer_cls is None:
        return
    if service.servicer_cls is None or not issubclass(
        service.servicer_cls, base.servicer_cls
    ):
        servicer = getattr(service.servicer_cls, "__qualname__", None)
        raise TypeError(
            f"{where}: the servicer {servicer} does not extend "
            f"{base.servicer_cls.__qualname__}"
        )
