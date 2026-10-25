"""The policies: an exception of the business logic and the status of a call."""

__all__ = ("BaseGrpcErrorPolicy",)

import logging
import typing as t

from google.rpc import status_pb2
from ingots.puer import Entity


class BaseGrpcErrorPolicy(Entity):
    """
    The policy of an exception of the business logic, a strategy: how a
    server encodes the exception into the status of the call and logs it.
    The RPCs raise their exceptions and see no protobuf: it lives in the
    policies. A client sees the status as a :class:`GrpcError`.

    A policy takes the exceptions of :attr:`EXCEPTION` and its subclasses.
    A server logs the exception at
    :attr:`LOG_LEVEL`: ``INFO`` for an answer of the API, ``ERROR`` for a
    fault of the server; with its traceback when :attr:`LOG_EXC_INFO`, as
    ``exc_info`` of :mod:`logging`. A class without :attr:`EXCEPTION` is a
    base of other policies. :class:`BaseStaticGrpcErrorPolicy` declares its
    status in constants.
    """

    EXCEPTION: t.ClassVar[type[Exception]]
    LOG_LEVEL: t.ClassVar[int] = logging.INFO
    LOG_EXC_INFO: t.ClassVar[bool] = False

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        check_policy(cls)

    @t.final
    def encode(self, error: Exception) -> status_pb2.Status:
        """The status of ``error``, of the business logic only."""
        return self._encode(error)

    def _encode(self, error: Exception) -> status_pb2.Status:
        """The status of an exception: an ``ErrorInfo`` among its details."""
        raise NotImplementedError(f"{type(self).__qualname__}._encode")


def check_policy(cls: type[BaseGrpcErrorPolicy]) -> None:
    """
    Internal, run when the class is created: the exception a policy declares
    is an exception class.
    """
    if "EXCEPTION" not in vars(cls):
        return
    if not (isinstance(cls.EXCEPTION, type) and issubclass(cls.EXCEPTION, Exception)):
        raise TypeError(
            f"{cls.__qualname__}.EXCEPTION: {cls.EXCEPTION!r} is no exception class"
        )
