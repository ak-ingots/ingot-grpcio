import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import typing as t
import unittest
from unittest import mock

from google.protobuf import descriptor_pb2

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServers
from ingot_grpcio.grpc.services import GrpcService, build_descriptor_set
from ingot_grpcio.grpc.services.export import iter_with_imports
from ingots.puer import Slot
from ingots.puer.cli import CommandRunner

from .proto import tst_pb2_grpc
from .test_server import Echo, Ping

# the wheel test installs the wheel alone, without the tools of development
HAS_PROTOC = importlib.util.find_spec("grpc_tools") is not None


class EchoGrpcServer(DefaultGrpcServer):
    echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)


class PingGrpcServer(DefaultGrpcServer):
    ping = GrpcService(tst_pb2_grpc.PingStub, Ping)


class TstGrpcServers(GrpcServers):
    default = Slot(EchoGrpcServer)
    ping = Slot(PingGrpcServer)


class TstGrpcUnit(GrpcUnit):
    servers = Slot(TstGrpcServers)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


def read(path: pathlib.Path) -> descriptor_pb2.FileDescriptorSet:
    return descriptor_pb2.FileDescriptorSet.FromString(path.read_bytes())


def find_file(
    descriptor_set: descriptor_pb2.FileDescriptorSet, name: str
) -> descriptor_pb2.FileDescriptorProto:
    [file] = [file for file in descriptor_set.file if file.name == name]
    return file


class BuildTestCase(unittest.TestCase):
    def test_the_set_has_the_services_and_their_imports(self) -> None:
        descriptor_set = build_descriptor_set(EchoGrpcServer.grpc_services_iter())
        self.assertEqual(
            [file.name for file in descriptor_set.file],
            ["google/protobuf/timestamp.proto", "tests/proto/tst.proto"],
        )
        file = find_file(descriptor_set, "tests/proto/tst.proto")
        self.assertEqual([service.name for service in file.service], ["Echo"])
        self.assertEqual(
            [message.name for message in file.message_type],
            ["EchoRequest", "EchoReply"],
        )

    def test_a_file_is_given_once_with_the_services_of_all(self) -> None:
        services = [
            *EchoGrpcServer.grpc_services_iter(),
            *PingGrpcServer.grpc_services_iter(),
        ]
        descriptor_set = build_descriptor_set(services)
        self.assertEqual(len(descriptor_set.file), 2)
        file = find_file(descriptor_set, "tests/proto/tst.proto")
        self.assertEqual([s.name for s in file.service], ["Echo", "Ping"])

    def test_a_file_imported_twice_is_given_once(self) -> None:
        file = EchoGrpcServer.echo.descriptor.file
        [timestamp] = file.dependencies
        names = [f.name for f in iter_with_imports([file, timestamp])]
        self.assertEqual(names, [timestamp.name, file.name])

    def test_no_services_give_an_empty_set(self) -> None:
        self.assertEqual(len(build_descriptor_set([]).file), 0)


class CommandTestCase(unittest.TestCase):
    @t.override
    def setUp(self) -> None:
        self.root = pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(mock.patch.dict(os.environ, clear=True))
        # the logging is not under test: keep the handlers of the test run
        self.enterContext(mock.patch("logging.config.dictConfig"))

    def export(self, *argv: str) -> int:
        output = str(self.root / "api.binpb")
        argv = ("--config", "IS_PRINT_CONFIGS=off", "grpc", "export", *argv)
        with contextlib.redirect_stderr(io.StringIO()):
            return CommandRunner(TstProject, [*argv, "--output", output]).run()

    def test_every_server_is_exported_by_default(self) -> None:
        with self.assertLogs("ingot_grpcio", "INFO") as logs:
            self.assertEqual(self.export(), 0)
        file = find_file(read(self.root / "api.binpb"), "tests/proto/tst.proto")
        self.assertEqual([s.name for s in file.service], ["Echo", "Ping"])
        self.assertIn(
            f"exported tst.Echo, tst.Ping of default, ping to {self.root}/api.binpb",
            logs.output[-1],
        )

    def test_the_servers_are_chosen(self) -> None:
        with self.assertLogs("ingot_grpcio", "INFO"):
            self.assertEqual(self.export("--server", "ping"), 0)
        file = find_file(read(self.root / "api.binpb"), "tests/proto/tst.proto")
        self.assertEqual([s.name for s in file.service], ["Ping"])
        with self.assertLogs("ingot_grpcio", "INFO"):
            self.assertEqual(self.export("--server", "ping", "--server", "default"), 0)
        file = find_file(read(self.root / "api.binpb"), "tests/proto/tst.proto")
        # in the order of the file
        self.assertEqual([s.name for s in file.service], ["Echo", "Ping"])

    def test_an_unknown_server_fails(self) -> None:
        with self.assertLogs(level="ERROR") as logs:
            self.assertEqual(self.export("--server", "nope"), 1)
        self.assertIn("no server nope in grpc.servers: default, ping", logs.output[-1])
        self.assertFalse((self.root / "api.binpb").exists())

    def test_servers_of_no_services_fail(self) -> None:
        output = str(self.root / "api.binpb")
        argv = ["--config", "IS_PRINT_CONFIGS=off", "grpc", "export"]
        with self.assertLogs(level="ERROR") as logs:
            code = CommandRunner(GrpcProject, [*argv, "--output", output]).run()
        self.assertEqual(code, 1)
        self.assertIn("nothing to export: no services in default", logs.output[-1])
        self.assertFalse((self.root / "api.binpb").exists())

    @unittest.skipUnless(HAS_PROTOC, "no grpcio-tools to generate the code")
    def test_protoc_generates_an_sdk_from_the_export(self) -> None:
        with self.assertLogs("ingot_grpcio", "INFO"):
            self.assertEqual(self.export("--server", "default"), 0)
        sdk = self.root / "sdk"
        sdk.mkdir()
        subprocess.run(
            [
                sys.executable,
                "-m",
                "grpc_tools.protoc",
                f"--descriptor_set_in={self.root / 'api.binpb'}",
                f"--python_out={sdk}",
                f"--grpc_python_out={sdk}",
                "tests/proto/tst.proto",
            ],
            check=True,
            capture_output=True,
            cwd=self.root,
        )
        generated = (sdk / "tests/proto/tst_pb2_grpc.py").read_text()
        self.assertIn("class EchoStub", generated)
        self.assertNotIn("class PingStub", generated)
