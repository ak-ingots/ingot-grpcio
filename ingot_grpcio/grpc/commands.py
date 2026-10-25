"""The commands of gRPC."""

__all__ = ("ExportGrpcCliArgs", "ExportGrpcCommand")

import argparse
import logging
import pathlib
import typing as t
from dataclasses import dataclass

from ingots.puer.cli import BaseCommand

from .servers import BaseGrpcServer
from .services import build_descriptor_set

if t.TYPE_CHECKING:
    from ingot_grpcio.project import GrpcProject

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExportGrpcCliArgs:
    servers: tuple[str, ...]
    output: pathlib.Path


class ExportGrpcCommand(BaseCommand):
    """
    Writes the services of servers of the project to a file, a
    ``FileDescriptorSet`` that ``protoc --descriptor_set_in`` or buf
    generate client SDKs from: those of every server of ``grpc.servers``,
    or of the servers given. Servers serving nothing export nothing: an
    error, not an empty SDK.
    """

    cli_description = "Exports the services of the servers for client SDKs."
    cli_args: ExportGrpcCliArgs
    project: "GrpcProject"

    @t.override
    @classmethod
    def _cli_prepare_parser(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--server",
            dest="grpc_export_servers",
            action="append",
            default=[],
            metavar="NAME",
            help="a server of grpc.servers, `default` for one; repeat for more; "
            "every server by default",
        )
        parser.add_argument(
            "--output",
            dest="grpc_export_output",
            required=True,
            type=pathlib.Path,
            metavar="PATH",
            help="the file to write, a binary FileDescriptorSet (.binpb)",
        )

    @t.override
    @classmethod
    def _cli_build_args(cls, namespace: argparse.Namespace) -> ExportGrpcCliArgs:
        return ExportGrpcCliArgs(
            tuple(namespace.grpc_export_servers), namespace.grpc_export_output
        )

    @t.override
    async def _run(self) -> None:
        slots = dict(self.project.grpc.servers.slots_iter(BaseGrpcServer))
        names = self.cli_args.servers or tuple(slots)
        unknown = [name for name in names if name not in slots]
        if unknown:
            raise LookupError(
                f"no server {', '.join(unknown)} in grpc.servers: "
                f"{', '.join(slots)}"
            )
        services = [
            service
            for name in names
            for service in slots[name].cls.grpc_services_iter()
        ]
        if not services:
            raise LookupError(f"nothing to export: no services in {', '.join(names)}")
        output = self.cli_args.output
        output.write_bytes(build_descriptor_set(services).SerializeToString())
        full_names = sorted({service.full_name for service in services})
        logger.info(
            "exported %s of %s to %s",
            ", ".join(full_names),
            ", ".join(names),
            output,
        )
