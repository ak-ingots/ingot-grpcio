"""The policy of the exceptions no other policy takes."""

__all__ = ("InternalGrpcErrorPolicy",)

import logging
import typing as t

import grpc

from .static import BaseStaticGrpcErrorPolicy


class InternalGrpcErrorPolicy(BaseStaticGrpcErrorPolicy):
    """
    The policy of every exception no other policy takes: ``INTERNAL``, with a
    message that tells nothing of the exception. Its text and traceback
    reach a client only in the ``DebugInfo`` a server may add.
    """

    EXCEPTION = Exception
    CODE = grpc.StatusCode.INTERNAL
    DOMAIN = "ingot_grpcio"
    REASON = "INTERNAL"
    LOG_LEVEL = logging.ERROR
    LOG_EXC_INFO = True

    @t.override
    def _get_message(self, error: Exception) -> str:
        return "internal error"
