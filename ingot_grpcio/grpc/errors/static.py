"""The static policies: the status of an exception declared in constants."""

__all__ = ("BaseStaticGrpcErrorPolicy",)

import typing as t

import grpc
from google.protobuf import any_pb2
from google.rpc import error_details_pb2, status_pb2

from .policies import BaseGrpcErrorPolicy

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from google.protobuf.message import Message


class BaseStaticGrpcErrorPolicy(BaseGrpcErrorPolicy):
    """
    A policy of one status for every exception it takes::

        class InsufficientFundsPolicy(BaseStaticGrpcErrorPolicy):
            EXCEPTION = InsufficientFunds
            CODE = grpc.StatusCode.FAILED_PRECONDITION
            DOMAIN = "shop.example.com"
            REASON = "INSUFFICIENT_FUNDS"

            @t.override
            def _get_metadata(self, error):
                return {"account": error.account}

    The status has :attr:`CODE`, the message of :meth:`_get_message`, an
    ``ErrorInfo`` of :attr:`DOMAIN`, :attr:`REASON` and
    :meth:`_get_metadata`, then the details of :meth:`_iter_details`.
    """

    CODE: t.ClassVar[grpc.StatusCode]
    DOMAIN: t.ClassVar[str]
    REASON: t.ClassVar[str]

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        check_static_policy(cls)

    @t.override
    def __repr__(self) -> str:
        reason = getattr(self, "REASON", "-")
        return f"<{type(self).__qualname__} {getattr(self, 'DOMAIN', '-')}/{reason}>"

    @t.final
    @t.override
    def _encode(self, error: Exception) -> status_pb2.Status:
        error_info = error_details_pb2.ErrorInfo(
            domain=self.DOMAIN, reason=self.REASON, metadata=self._get_metadata(error)
        )
        details: list[Message] = [error_info, *self._iter_details(error)]
        status = status_pb2.Status(
            code=self.CODE.value[0], message=self._get_message(error)
        )
        for detail in details:
            packed = any_pb2.Any()
            packed.Pack(detail)
            status.details.append(packed)
        return status

    def _get_message(self, error: Exception) -> str:
        """The message of the status: the text of the exception by default."""
        return str(error)

    def _get_metadata(self, error: Exception) -> dict[str, str]:
        """The metadata of the ``ErrorInfo``: none by default."""
        return {}

    def _iter_details(self, error: Exception) -> "Iterator[Message]":
        """Other details of the status, such as a ``BadRequest``: none."""
        return iter(())


def check_static_policy(cls: type[BaseStaticGrpcErrorPolicy]) -> None:
    """
    Internal, run when the class is created: a static policy declaring
    :attr:`BaseGrpcErrorPolicy.EXCEPTION` declares the rest of its status.
    """
    if "EXCEPTION" not in vars(cls):
        return
    missing = [name for name in ("CODE", "DOMAIN", "REASON") if not hasattr(cls, name)]
    if missing:
        raise TypeError(f"{cls.__qualname__} declares no {', '.join(missing)}")
