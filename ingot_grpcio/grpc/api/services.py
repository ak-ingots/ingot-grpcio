"""The services of the API and the servicers implementing them."""

__all__ = ("GrpcService", "GrpcServicer")

import typing as t

from google.protobuf import descriptor_pool
from ingots.puer import Entity

if t.TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

    from google.protobuf.descriptor import ServiceDescriptor
    from grpc import aio


class GrpcServicer(Entity):
    """
    A servicer: the implementation of the RPCs of a service, extending the
    generated base class too. It reaches the project as any entity does::

        class Greeter(GrpcServicer, demo_pb2_grpc.GreeterServicer):
            @t.override
            async def SayHello(self, request, context): ...

    A :class:`GrpcService` names it and creates it.
    """


class GrpcService(Entity):
    """
    A service: the contract of a ``.proto`` file, in a slot of
    :class:`~ingot_grpcio.grpc.api.GrpcApi`. A subclass names the service
    and its ``_pb2_grpc`` module as arguments of the class, and the class
    finds the rest by the names grpcio generates when it is created:
    :attr:`DESCRIPTOR`, :attr:`SERVICER_BASE` (``GreeterServicer``),
    :attr:`STUB` (``GreeterStub``) and ``add_GreeterServicer_to_server``::

        class GreeterService(
            GrpcService, full_name="demo.Greeter", module=demo_pb2_grpc
        ):
            SERVICER = Greeter

    :attr:`SERVICER`, the implementation, is optional: a contract alone
    gives the stub to the clients of a server written in anything, and no
    server of the project serves it. It must extend :attr:`SERVICER_BASE`.
    A refined implementation (``AppGreeter(Greeter)``) is a subclass of the
    service; another one altogether is a subclass of the contract, the
    service without a servicer. A class with no service named is a base of
    other services.

    :raises LookupError: no such service, or the module is not its own.
    """

    SERVICER: t.ClassVar[type[GrpcServicer]]

    # kept when the class is created
    FULL_NAME: t.ClassVar[str]
    MODULE: t.ClassVar["ModuleType"]
    DESCRIPTOR: t.ClassVar["ServiceDescriptor"]
    SERVICER_BASE: t.ClassVar[type[object]]
    STUB: t.ClassVar[type[object]]

    _servicer: GrpcServicer

    @t.override
    @classmethod
    def __init_subclass__(
        cls,
        *,
        full_name: str | None = None,
        module: "ModuleType | None" = None,
        **kwargs: t.Any,
    ) -> None:
        super().__init_subclass__(**kwargs)
        if full_name is not None or module is not None:
            find_generated_code(cls, full_name, module)
        check_servicer(cls)

    @t.final
    @property
    def servicer(self) -> GrpcServicer:
        """
        The servicer, created on the first use: one for every server serving
        the service.

        :raises LookupError: the service has no implementation.
        """
        try:
            return self._servicer
        except AttributeError:
            try:
                servicer_cls = self.SERVICER
            except AttributeError:
                raise LookupError(
                    f"{self!r} has no SERVICER: nothing implements it"
                ) from None
            self._servicer = servicer_cls(self.project)
            return self._servicer

    @t.override
    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {getattr(self, 'FULL_NAME', '-')}>"

    def add_to_server(self, server: "aio.Server") -> None:
        """
        Adds the servicer to a server, as grpcio generates it.

        :raises LookupError: the service has no implementation.
        """
        name = f"add_{self.DESCRIPTOR.name}Servicer_to_server"
        registrar: Callable[[object, aio.Server], None] = getattr(self.MODULE, name)
        registrar(self.servicer, server)


def find_generated_code(
    cls: type[GrpcService], full_name: str | None, module: "ModuleType | None"
) -> None:
    """
    Internal, run when the class is created: the service named by the
    arguments of the class is in a ``.proto`` file and ``module`` is its
    generated code, which the class keeps.
    """
    if full_name is None or module is None:
        raise TypeError(f"{cls.__qualname__}: full_name and module go together")
    try:
        descriptor = descriptor_pool.Default().FindServiceByName(full_name)
    except KeyError:
        raise LookupError(
            f"{cls.__qualname__}: no gRPC service {full_name!r}: import its "
            f"_pb2_grpc module first"
        ) from None
    name = descriptor.name
    servicer_base_name = f"{name}Servicer"
    stub_name = f"{name}Stub"
    registrar_name = f"add_{name}Servicer_to_server"
    names = (servicer_base_name, stub_name, registrar_name)
    missing = [attr for attr in names if not hasattr(module, attr)]
    if missing:
        raise LookupError(
            f"{cls.__qualname__}: {module.__name__} is not the _pb2_grpc module "
            f"of {full_name!r}: no {', '.join(missing)}"
        )
    cls.FULL_NAME, cls.MODULE, cls.DESCRIPTOR = full_name, module, descriptor
    cls.SERVICER_BASE = getattr(module, servicer_base_name)
    cls.STUB = getattr(module, stub_name)


def check_servicer(cls: type[GrpcService]) -> None:
    """
    Internal, run when the class is created: the servicer of a service is a
    :class:`GrpcServicer` extending the generated base of the service.
    """
    servicer_cls = getattr(cls, "SERVICER", None)
    if servicer_cls is None:
        return
    if not (isinstance(servicer_cls, type) and issubclass(servicer_cls, GrpcServicer)):
        raise TypeError(
            f"{cls.__qualname__}.SERVICER: {servicer_cls!r} is no GrpcServicer"
        )
    if not hasattr(cls, "DESCRIPTOR"):
        raise TypeError(f"{cls.__qualname__}: a SERVICER of no service")
    if not issubclass(servicer_cls, cls.SERVICER_BASE):
        raise TypeError(
            f"{cls.__qualname__}.SERVICER: {servicer_cls.__qualname__} does not "
            f"extend {cls.SERVICER_BASE.__qualname__}, the servicer base of "
            f"{cls.FULL_NAME!r}"
        )
