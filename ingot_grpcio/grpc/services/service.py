"""The service: a contract of gRPC as an attribute of a server or a client."""

__all__ = ("GrpcService",)

import sys
import typing as t
from types import ModuleType

from google.protobuf.descriptor import FileDescriptor

from .servicer import GrpcServicer

if t.TYPE_CHECKING:
    from collections.abc import Callable

    from google.protobuf.descriptor import ServiceDescriptor
    from grpc import aio
    from ingots.puer import Project

    from ingot_grpcio.grpc.clients import BaseGrpcClient
    from ingot_grpcio.grpc.servers import BaseGrpcServer

    from .owner import GrpcServicesOwner


class GrpcService[Stub, Servicer: GrpcServicer]:
    """
    A service of gRPC, an attribute of a class: the contract of a ``.proto``
    file, by the stub grpcio generates for it, and the servicer implementing
    it, if any. A binding declares the services of a server, and the server
    and its client extend it::

        class AppGrpcBinding:
            echo = GrpcService(demo_pb2_grpc.EchoStub, Echo)


        class AppGrpcServer(AppGrpcBinding, DefaultGrpcServer):
            pass


        class AppGrpcClient(AppGrpcBinding, DefaultGrpcClient):
            pass

    ``server.echo`` is the servicer of the server, created once with the
    project; ``client.echo`` the stub on the channel of the client, created
    once when the client is configured, typed as the async stub that
    mypy-protobuf generates; ``AppGrpcBinding.echo`` the service itself.
    From the stub the service finds the rest of the generated code by the
    names grpcio gives it: the descriptor, the servicer base and the
    function adding a servicer to a server.

    A contract alone, with no servicer, serves a client of a server written
    in anything; a server refuses it.

    :raises LookupError: the stub is not one grpcio generates.
    :raises TypeError: the servicer is no :class:`GrpcServicer` extending
        the servicer base of the service.
    """

    _name: str

    @t.overload
    def __init__(
        self: "GrpcService[Stub, t.Never]", stub_cls: "Callable[[aio.Channel], Stub]"
    ) -> None: ...

    @t.overload
    def __init__(
        self, stub_cls: "Callable[[aio.Channel], Stub]", servicer_cls: type[Servicer]
    ) -> None: ...

    def __init__(
        self,
        stub_cls: "Callable[[aio.Channel], Stub]",
        servicer_cls: type[Servicer] | None = None,
    ) -> None:
        self._stub_cls = stub_cls
        self._module, self._descriptor = find_generated_code(stub_cls)
        self._servicer_cls = servicer_cls
        check_servicer(self)

    @t.final
    @property
    def name(self) -> str:
        """The name of the attribute, ``echo``: the same in every class."""
        return self._name

    @t.final
    @property
    def full_name(self) -> str:
        """The full name of the service, ``demo.Echo``."""
        return self._descriptor.full_name

    @t.final
    @property
    def descriptor(self) -> "ServiceDescriptor":
        """The descriptor of the service, its methods and messages."""
        return self._descriptor

    @t.final
    @property
    def servicer_base(self) -> type[object]:
        """The base class of the servicers that grpcio generates."""
        return t.cast(type[object], getattr(self._module, self._servicer_base_name))

    @t.final
    @property
    def servicer_cls(self) -> type[Servicer] | None:
        """The implementation of the service, or ``None`` for a contract."""
        return self._servicer_cls

    @property
    def _servicer_base_name(self) -> str:
        return f"{self._descriptor.name}Servicer"

    def __set_name__(self, owner: type, name: str) -> None:
        if getattr(self, "_name", name) != name:
            raise TypeError(
                f"{owner.__qualname__}.{name}: {self!r} is already {self._name}"
            )
        self._name = name

    @t.overload
    def __get__(self, obj: None, owner: type) -> t.Self: ...

    @t.overload
    def __get__(self, obj: "BaseGrpcServer", owner: type) -> Servicer: ...

    @t.overload
    def __get__(self, obj: "BaseGrpcClient", owner: type) -> Stub: ...

    def __get__(self, obj: "GrpcServicesOwner | None", owner: type) -> object:
        if obj is None:
            return self
        return obj._grpc_services_get(self)

    @t.override
    def __repr__(self) -> str:
        return f"<{type(self).__qualname__} {self.full_name}>"

    @t.final
    def build_stub(self, channel: "aio.Channel") -> Stub:
        """The stub of the service on a channel."""
        return self._stub_cls(channel)

    @t.final
    def build_servicer(self, project: "Project") -> Servicer:
        """
        The servicer of the service, of the project.

        :raises LookupError: the service has no implementation.
        """
        if self._servicer_cls is None:
            raise LookupError(f"{self!r} has no servicer: nothing implements it")
        return self._servicer_cls(project)

    @t.final
    def add_to_server(self, servicer: Servicer, server: "aio.Server") -> None:
        """Adds a servicer of the service to a server, as grpcio generates it."""
        name = f"add_{self._servicer_base_name}_to_server"
        registrar: Callable[[object, aio.Server], None] = getattr(self._module, name)
        registrar(servicer, server)


def find_generated_code(
    stub_cls: "Callable[[aio.Channel], object]",
) -> tuple[ModuleType, "ServiceDescriptor"]:
    """
    Internal: the ``_pb2_grpc`` module of a stub, and the descriptor of its
    service in the ``_pb2`` module that the generated code imports.
    """
    module = sys.modules.get(getattr(stub_cls, "__module__", ""))
    name = getattr(stub_cls, "__name__", "").removesuffix("Stub")
    for value in vars(module).values() if module else ():
        file = getattr(value, "DESCRIPTOR", None)
        if isinstance(file, FileDescriptor) and name in file.services_by_name:
            return t.cast(ModuleType, module), file.services_by_name[name]
    raise LookupError(f"{stub_cls!r} is not a stub that grpcio generates")


def check_servicer(service: GrpcService[t.Any, t.Any]) -> None:
    """
    Internal: the servicer of a service is a :class:`GrpcServicer`
    extending the generated base of the service.
    """
    servicer_cls = service.servicer_cls
    if servicer_cls is None:
        return
    if not (isinstance(servicer_cls, type) and issubclass(servicer_cls, GrpcServicer)):
        raise TypeError(
            f"{service!r}: the servicer {servicer_cls!r} is no GrpcServicer"
        )
    base = service.servicer_base
    if not issubclass(servicer_cls, base):
        raise TypeError(
            f"{service!r}: the servicer {servicer_cls.__qualname__} does not "
            f"extend {base.__qualname__}"
        )
