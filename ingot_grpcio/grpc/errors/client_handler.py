"""The handler of the errors of a client: it decodes a failed call."""

__all__ = ("ClientGrpcErrorHandler",)

import logging
import typing as t

from google.rpc import status_pb2
from ingots.puer import Entity

from .error import GrpcError

if t.TYPE_CHECKING:
    from grpc import aio

logger = logging.getLogger(__name__)


class ClientGrpcErrorHandler(Entity):
    """
    Turns a failed call of a client into a :class:`GrpcError`, its code,
    message and ``ErrorInfo`` at hand: the server classes of the exceptions
    stay on the server. A project changes how, its logging for one, in a
    subclass::

        class AppGrpcErrors(GrpcErrors):
            client_handler = Slot(AppClientGrpcErrorHandler)
    """

    @t.final
    def handle(self, error: "aio.AioRpcError", method: str) -> GrpcError:
        """Decodes a failed call of ``method`` and logs it: the error to raise."""
        decoded = self.decode_rpc_error(error)
        self._log(decoded, method)
        return decoded

    @t.final
    def decode(self, status: status_pb2.Status) -> GrpcError:
        """The error of a status, as a client sees it."""
        return GrpcError.from_status(status)

    @t.final
    def decode_rpc_error(self, error: "aio.AioRpcError") -> GrpcError:
        """
        The error of a failed call, by :meth:`decode`: of the status the
        server sent with its details, or of the code and message alone when
        it sent none, as a call that never reached a server.
        """
        details = dict(error.trailing_metadata() or ()).get(STATUS_DETAILS_KEY)
        if isinstance(details, bytes):
            return self.decode(status_pb2.Status.FromString(details))
        code, message = error.code().value[0], error.details() or ""
        return self.decode(status_pb2.Status(code=code, message=message))

    def _log(self, error: GrpcError, method: str) -> None:
        """
        Logs a failed call at ``DEBUG``, with its code, domain and reason:
        the caller decides what the error means to it.
        """
        logger.debug(
            "%s: %s %r, %s/%s",
            method,
            error.code.name,
            error.message,
            error.domain,
            error.reason,
        )


# the trailing metadata of a status with its details, as grpcio-status sends it
STATUS_DETAILS_KEY = "grpc-status-details-bin"
