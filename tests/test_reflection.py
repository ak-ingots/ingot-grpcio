import os
import subprocess
import sys
import typing as t
import unittest
from unittest import mock

import grpc
from google.protobuf import descriptor_pb2
from grpc import aio
from grpc_reflection.v1alpha import reflection_pb2, reflection_pb2_grpc

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServers
from ingot_grpcio.grpc.services import GrpcService
from ingots.puer import Slot

from .proto import tst_pb2_grpc
from .test_server import Echo

Request: t.TypeAlias = reflection_pb2.ServerReflectionRequest
Response: t.TypeAlias = reflection_pb2.ServerReflectionResponse


class EchoGrpcServer(DefaultGrpcServer):
    echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)


class TstGrpcServers(GrpcServers):
    default = Slot(EchoGrpcServer)


class TstGrpcUnit(GrpcUnit):
    servers = Slot(TstGrpcServers)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


class ServerFixture(unittest.IsolatedAsyncioTestCase):
    @t.override
    async def asyncSetUp(self) -> None:
        self.enterContext(
            mock.patch.dict(
                os.environ,
                {
                    "INGOT_GRPC_DEFAULT_LISTEN_HOST": "127.0.0.1",
                    "INGOT_GRPC_DEFAULT_PORT": "0",
                    "INGOT_IS_PRINT_CONFIGS": "off",
                },
                clear=True,
            )
        )
        # the logging is not under test: keep the handlers of the test run
        self.enterContext(mock.patch("logging.config.dictConfig"))

    async def start(self) -> str:
        project = TstProject()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        with self.assertLogs("ingot_grpcio", "INFO") as logs:
            server = await project.grpc.servers.default
        [address] = server.addresses
        channel = aio.insecure_channel(address)
        self.addAsyncCleanup(channel.close)
        self.stub = reflection_pb2_grpc.ServerReflectionStub(channel)
        return "\n".join(logs.output)

    async def ask(self, request: Request) -> Response:
        call = self.stub.ServerReflectionInfo(iter([request]))
        [response] = [response async for response in call]
        return response


class ReflectionTestCase(ServerFixture):
    @t.override
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        os.environ["INGOT_GRPC_DEFAULT_IS_REFLECTION"] = "on"
        self.logs = await self.start()

    async def test_the_server_lists_what_it_serves(self) -> None:
        response = await self.ask(Request(list_services=""))
        names = {s.name for s in response.list_services_response.service}
        self.assertEqual(
            names, {"tst.Echo", "grpc.reflection.v1alpha.ServerReflection"}
        )
        self.assertRegex(self.logs, r"<EchoGrpcServer 127\.0\.0\.1:\d+>: reflection on")

    async def test_a_file_tells_only_the_services_served(self) -> None:
        response = await self.ask(Request(file_containing_symbol="tst.Echo"))
        files = [
            descriptor_pb2.FileDescriptorProto.FromString(data)
            for data in response.file_descriptor_response.file_descriptor_proto
        ]
        [file] = [file for file in files if file.name == "tests/proto/tst.proto"]
        self.assertEqual([service.name for service in file.service], ["Echo"])
        self.assertEqual(
            [message.name for message in file.message_type],
            ["EchoRequest", "EchoReply"],
        )

    async def test_a_service_not_served_is_not_found(self) -> None:
        response = await self.ask(Request(file_containing_symbol="tst.Ping"))
        self.assertEqual(
            response.error_response.error_code, grpc.StatusCode.NOT_FOUND.value[0]
        )


class OffTestCase(ServerFixture):
    async def test_the_reflection_is_off_by_default(self) -> None:
        logs = await self.start()
        self.assertNotIn("reflection on", logs)
        with self.assertRaises(aio.AioRpcError) as raised:
            await self.ask(Request(list_services=""))
        self.assertEqual(raised.exception.code(), grpc.StatusCode.UNIMPLEMENTED)

    async def test_without_the_extra_the_server_tells_how_to_install(self) -> None:
        os.environ["INGOT_GRPC_DEFAULT_IS_REFLECTION"] = "on"
        name = "ingot_grpcio.grpc.servers.reflection"
        hidden = {"grpc_reflection": None, "grpc_reflection.v1alpha": None}
        with mock.patch.dict(sys.modules, hidden):  # import grpc_reflection fails
            sys.modules.pop(name, None)  # restored on exit
            with self.assertRaisesRegex(
                ImportError, r'pip install "ingot-grpcio\[reflection\]"$'
            ):
                await self.start()


class ImportTestCase(unittest.TestCase):
    def test_the_package_imports_no_reflection(self) -> None:
        # grpcio imports grpc_reflection itself when installed: check ours
        code = (
            "import sys, ingot_grpcio, ingot_grpcio.grpc.servers; "
            "print('ingot_grpcio.grpc.servers.reflection' in sys.modules)"
        )
        done = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True
        )
        self.assertEqual(done.stdout, "False\n")
