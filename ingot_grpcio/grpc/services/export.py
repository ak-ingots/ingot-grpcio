"""The export of services: the descriptors client SDKs are generated from."""

__all__ = ("build_descriptor_set",)

import typing as t

from google.protobuf import descriptor_pb2

if t.TYPE_CHECKING:
    from collections.abc import Iterable

    from google.protobuf.descriptor import FileDescriptor

    from .service import GrpcService


def build_descriptor_set(
    services: "Iterable[GrpcService[t.Any, t.Any]]",
) -> descriptor_pb2.FileDescriptorSet:
    """
    The ``FileDescriptorSet`` of services, complete as ``protoc
    --include_imports`` writes one: the files declaring them and every file
    they import, the imports first. A file keeps only the given services,
    its messages all: an SDK shows what a server serves, nothing else.
    """
    services_by_file: dict[str, set[str]] = {}
    files: list[FileDescriptor] = []
    for service in services:
        file = service.descriptor.file
        if file.name not in services_by_file:
            files.append(file)
        services_by_file.setdefault(file.name, set()).add(service.descriptor.name)
    descriptor_set = descriptor_pb2.FileDescriptorSet()
    for file in iter_with_imports(files):
        proto = descriptor_set.file.add()
        file.CopyToProto(proto)
        names = services_by_file.get(file.name, set())
        kept = [service for service in proto.service if service.name in names]
        del proto.service[:]
        proto.service.extend(kept)
    return descriptor_set


def iter_with_imports(files: "Iterable[FileDescriptor]") -> "list[FileDescriptor]":
    """Internal: files with every file they import, each once, imports first."""
    ordered: list[FileDescriptor] = []
    seen: set[str] = set()

    def visit(file: "FileDescriptor") -> None:
        if file.name in seen:
            return
        seen.add(file.name)
        for dependency in file.dependencies:
            visit(dependency)
        ordered.append(file)

    for file in files:
        visit(file)
    return ordered
