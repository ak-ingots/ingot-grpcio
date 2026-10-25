"""The handler of the errors: it applies the policies of the project."""

__all__ = ("GrpcErrorHandler",)

import logging
import traceback
import typing as t

from google.rpc import error_details_pb2, status_pb2
from ingots.puer import Entity

from .policies import BaseGrpcErrorPolicy
from .error import GrpcError

if t.TYPE_CHECKING:
    from grpc import aio

    from ingot_grpcio.project import GrpcProject

logger = logging.getLogger(__name__)


class GrpcErrorHandler(Entity):
    """
    Applies the policies of ``grpc.errors``: a server handles an exception
    by the policy of its class, or of the nearest base class that has one;
    a client decodes a status into a :class:`GrpcError`, its code, message
    and ``ErrorInfo`` at hand. A project changes how they are applied, its
    logging for one, in a subclass::

        class AppGrpcErrors(GrpcErrors):
            handler = Slot(AppGrpcErrorHandler)
    """

    project: "GrpcProject"

    @t.final
    def find_policy(self, error: Exception) -> BaseGrpcErrorPolicy:
        """The policy of an exception, by the classes of its MRO."""
        errors = self.project.grpc.errors
        for klass in type(error).__mro__:
            if name := errors._policies_by_exception.get(klass):
                return errors.slots_find_entity(name, BaseGrpcErrorPolicy)
        raise AssertionError(f"{errors!r}: no policy of Exception")  # pragma: no cover

    @t.final
    def handle(
        self, error: Exception, method: str, *, is_debug_info: bool = False
    ) -> status_pb2.Status:
        """
        Logs an exception ``method`` raised and encodes it, both by its
        policy: the status a server sends. With ``is_debug_info``, the status
        has a ``DebugInfo`` of the traceback too, which tells a client the
        internals of the server: a policy cannot add one.
        """
        policy = self.find_policy(error)
        status = policy.encode(error)
        self._log(error, method, policy, status)
        if is_debug_info:
            status.details.add().Pack(build_debug_info(error))
        return status

    @t.final
    def decode(self, status: status_pb2.Status) -> GrpcError:
        """The error of a status, as a client sees it."""
        return GrpcError.from_status(status)

    @t.final
    def decode_rpc_error(self, error: "aio.AioRpcError") -> GrpcError:
        """
        The error of a failed call, by :meth:`decode`: of the status the
        server sent with its details, or of the code and message alone when
        it sent none.
        """
        details = dict(error.trailing_metadata() or ()).get(STATUS_DETAILS_KEY)
        if isinstance(details, bytes):
            return self.decode(status_pb2.Status.FromString(details))
        code, message = error.code().value[0], error.details() or ""
        return self.decode(status_pb2.Status(code=code, message=message))

    def _log(
        self,
        error: Exception,
        method: str,
        policy: BaseGrpcErrorPolicy,
        status: status_pb2.Status,
    ) -> None:
        """
        Logs an exception in a line with the domain and reason of its
        status, at the ``LOG_LEVEL`` of its policy, with its traceback when
        the policy has ``LOG_EXC_INFO``.
        """
        sent = GrpcError.from_status(status)
        logger.log(
            policy.LOG_LEVEL,
            "%s: %r, %s/%s",
            method,
            error,
            sent.domain,
            sent.reason,
            exc_info=error if policy.LOG_EXC_INFO else None,
        )


def build_debug_info(error: BaseException) -> error_details_pb2.DebugInfo:
    """Internal: the ``DebugInfo`` of an exception, its traceback included."""
    return error_details_pb2.DebugInfo(
        stack_entries=traceback.format_tb(error.__traceback__),
        detail=f"{type(error).__qualname__}: {error}",
    )


# the trailing metadata of a status with its details, as grpcio-status sends it
STATUS_DETAILS_KEY = "grpc-status-details-bin"
