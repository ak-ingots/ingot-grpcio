"""The binding of every service of the API."""

__all__ = ("AutoGrpcBinding",)

import typing as t

from ingot_grpcio.grpc.api import GrpcService

from .base import BaseGrpcBinding

if t.TYPE_CHECKING:
    from collections.abc import Iterator

    from ingot_grpcio.project import GrpcProject


class AutoGrpcBinding(BaseGrpcBinding):
    """Every service of ``grpc.api`` that has an implementation."""

    project: "GrpcProject"

    @t.override
    def _iter_services(self) -> "Iterator[GrpcService]":
        api = self.project.grpc.api
        for name, slot in api.slots_iter(GrpcService):
            if hasattr(slot.cls, "SERVICER"):
                yield api.slots_find_entity(name, GrpcService)
