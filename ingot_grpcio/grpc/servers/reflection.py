"""The reflection of a server: the only module importing grpcio-reflection."""

__all__ = ("enable_reflection",)

import typing as t

from google.protobuf import descriptor_pool

from ingot_grpcio.grpc.services import build_descriptor_set

try:
    from grpc_reflection.v1alpha import reflection
except ImportError:
    raise ImportError(
        "the reflection of a server needs grpcio-reflection: "
        'pip install "ingot-grpcio[reflection]"'
    ) from None

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    from grpc import aio

    from ingot_grpcio.grpc.services import GrpcService


def enable_reflection(
    server: "aio.Server", services: "Iterable[GrpcService[t.Any, t.Any]]"
) -> None:
    """
    Adds the reflection of gRPC to a server: visual clients such as grpcurl,
    grpcui or Postman find its RPCs and messages without the ``.proto``
    files. It describes exactly the services given, from the set that
    ``grpc export`` writes: grpcio would tell their files whole.
    """
    pool = descriptor_pool.DescriptorPool()
    services = list(services)
    for file in build_descriptor_set(services).file:
        pool.Add(file)
    names = (*(service.full_name for service in services), reflection.SERVICE_NAME)
    reflection.enable_server_reflection(names, server, pool=pool)
