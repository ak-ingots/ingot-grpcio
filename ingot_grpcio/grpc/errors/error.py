"""The error of a failed call, as a client sees it."""

__all__ = ("GrpcError",)

import typing as t

import grpc
from google.rpc import error_details_pb2

if t.TYPE_CHECKING:
    from google.protobuf.message import Message
    from google.rpc import status_pb2


class GrpcError(Exception):
    """
    A call failed with a status: its code, message and ``ErrorInfo`` as
    properties, its other details through
    :meth:`find_detail`. The status itself is :attr:`status`, for the rare
    caller that needs it.
    """

    @classmethod
    def from_status(cls, status: "status_pb2.Status") -> t.Self:
        """The error of a status."""
        return cls(status.message, status)

    @property
    def status(self) -> "status_pb2.Status":
        """The status of the call, as the server sent it."""
        return t.cast("status_pb2.Status", self.args[1])

    @property
    def code(self) -> grpc.StatusCode:
        """The code of the status."""
        return find_code(self.status.code)

    @property
    def message(self) -> str:
        """The message of the status: for a developer, not for a user."""
        return self.status.message

    @property
    def domain(self) -> str:
        """The domain of the ``ErrorInfo``: empty without one."""
        return self._error_info.domain

    @property
    def reason(self) -> str:
        """The reason of the ``ErrorInfo``: empty without one."""
        return self._error_info.reason

    @property
    def metadata(self) -> dict[str, str]:
        """The metadata of the ``ErrorInfo``: empty without one."""
        return dict(self._error_info.metadata)

    @property
    def _error_info(self) -> error_details_pb2.ErrorInfo:
        return self.find_detail(error_details_pb2.ErrorInfo) or (
            error_details_pb2.ErrorInfo()
        )

    @t.override
    def __str__(self) -> str:
        return t.cast(str, self.args[0])

    def find_detail[MessageType: "Message"](
        self, kind: type[MessageType]
    ) -> MessageType | None:
        """The first detail of the status of ``kind``, or ``None``."""
        for packed in self.status.details:
            if packed.TypeName() == kind.DESCRIPTOR.full_name:
                detail = kind()
                packed.Unpack(detail)
                return detail
        return None


def find_code(number: int) -> grpc.StatusCode:
    """Internal: the code of grpcio for the number of a status."""
    for code in grpc.StatusCode:
        if code.value[0] == number:
            return code
    return grpc.StatusCode.UNKNOWN
