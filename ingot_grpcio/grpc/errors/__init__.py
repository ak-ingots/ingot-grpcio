"""The errors: the policies of the exceptions of the business logic."""

__all__ = (
    "BaseGrpcErrorPolicy",
    "BaseStaticGrpcErrorPolicy",
    "ClientGrpcErrorHandler",
    "GrpcError",
    "GrpcErrors",
    "InternalGrpcErrorPolicy",
    "ServerGrpcErrorHandler",
)

import typing as t

from ingots.puer import Slot, Unit

from .client_handler import ClientGrpcErrorHandler
from .error import GrpcError
from .internal import InternalGrpcErrorPolicy
from .policies import BaseGrpcErrorPolicy
from .server_handler import ServerGrpcErrorHandler
from .static import BaseStaticGrpcErrorPolicy


class GrpcErrors(Unit):
    """
    The policies of the project, each in a slot of its own, and their
    handlers: :attr:`server_handler` finds them by the class of an
    exception, :attr:`client_handler` turns a failed call into a
    :class:`GrpcError`. :attr:`internal` takes every exception no other
    policy takes::

        class AppGrpcErrors(GrpcErrors):
            insufficient_funds = Slot(InsufficientFundsPolicy)

    An exception class has one policy, and so has a domain and reason.
    """

    server_handler = Slot(ServerGrpcErrorHandler)
    client_handler = Slot(ClientGrpcErrorHandler)
    internal = Slot(InternalGrpcErrorPolicy)

    _policies_by_exception: t.ClassVar[dict[type[Exception], str]]

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        index_policies(cls)


def index_policies(cls: type[GrpcErrors]) -> None:
    """
    Internal, run when the class is created: every policy declares its
    exception, and none shares an exception, or a static one a domain and
    reason, with another; the index of the class finds them by exception.
    """
    by_exception: dict[type[Exception], str] = {}
    by_reason: dict[tuple[str, str], str] = {}
    for name, slot in cls.slots_iter(BaseGrpcErrorPolicy):
        policy = slot.cls
        if not hasattr(policy, "EXCEPTION"):
            raise TypeError(
                f"{cls.__qualname__}.{name}: {policy.__qualname__} declares no "
                f"EXCEPTION"
            )
        owner = by_exception.setdefault(policy.EXCEPTION, name)
        if owner != name:
            raise TypeError(
                f"{cls.__qualname__}: {policy.EXCEPTION.__qualname__} has both "
                f"{owner} and {name}"
            )
        if issubclass(policy, BaseStaticGrpcErrorPolicy):
            key = (policy.DOMAIN, policy.REASON)
            owner = by_reason.setdefault(key, name)
            if owner != name:
                raise TypeError(
                    f"{cls.__qualname__}: {key[0]}/{key[1]} has both {owner} and "
                    f"{name}"
                )
    cls._policies_by_exception = by_exception


index_policies(GrpcErrors)  # __init_subclass__ runs for the subclasses only
