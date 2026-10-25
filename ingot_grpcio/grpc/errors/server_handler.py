"""The handler of the errors of a server: it applies the policies."""

__all__ = ("ServerGrpcErrorHandler",)

import logging
import traceback
import typing as t

from google.rpc import error_details_pb2, status_pb2
from ingots.puer import Entity

from .error import GrpcError
from .policies import BaseGrpcErrorPolicy

if t.TYPE_CHECKING:
    from ingot_grpcio.project import GrpcProject

logger = logging.getLogger(__name__)


class ServerGrpcErrorHandler(Entity):
    """
    Applies the policies of ``grpc.errors`` on a server: it handles an
    exception by the policy of its class, or of the nearest base class that
    has one. A project changes how they are applied, its logging for one,
    in a subclass::

        class AppGrpcErrors(GrpcErrors):
            server_handler = Slot(AppServerGrpcErrorHandler)
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
