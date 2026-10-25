import asyncio
import contextlib
import io
import os
import typing as t
import unittest
from collections.abc import AsyncIterator
from unittest import mock

import grpc
from grpc import aio

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.api import GrpcApi, GrpcService, GrpcServicer
from ingot_grpcio.grpc.bindings import AutoGrpcBinding, GrpcBindings
from ingot_grpcio.grpc.servers import DefaultGrpcServer
from ingots.puer import Slot
from ingots.puer.cli import CommandRunner

from .proto import tst_pb2_grpc
from .proto.tst_pb2 import EchoReply, EchoRequest

Context: t.TypeAlias = aio.ServicerContext[EchoRequest, EchoReply]


class Echo(GrpcServicer, tst_pb2_grpc.EchoServicer):
    @t.override
    async def Unary(self, request: EchoRequest, context: Context) -> EchoReply:
        if request.text == "slow":
            await asyncio.sleep(0.2)
        return EchoReply(text=request.text)

    @t.override
    async def ClientStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> EchoReply:
        return EchoReply(text=".".join([r.text async for r in request_iterator]))

    @t.override
    async def ServerStream(
        self, request: EchoRequest, context: Context
    ) -> AsyncIterator[EchoReply]:
        for part in request.text.split("."):
            yield EchoReply(text=part)

    @t.override
    async def BidiStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> AsyncIterator[EchoReply]:
        async for request in request_iterator:
            yield EchoReply(text=request.text.upper())


class Ping(GrpcServicer, tst_pb2_grpc.PingServicer):
    @t.override
    async def Ping(self, request: EchoRequest, context: Context) -> EchoReply:
        return EchoReply(text="pong")


class EchoService(GrpcService, full_name="tst.Echo", module=tst_pb2_grpc):
    SERVICER = Echo


class PingService(GrpcService, full_name="tst.Ping", module=tst_pb2_grpc):
    SERVICER = Ping


class TstGrpcApi(GrpcApi):
    echo = Slot(EchoService)
    ping = Slot(PingService)


class TstGrpcUnit(GrpcUnit):
    api = Slot(TstGrpcApi)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


async def requests(*texts: str) -> AsyncIterator[EchoRequest]:
    for text in texts:
        yield EchoRequest(text=text)


class ServerTestCase(unittest.IsolatedAsyncioTestCase):
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

    async def start(
        self, project_cls: type[GrpcProject] = TstProject
    ) -> tuple[GrpcProject, DefaultGrpcServer]:
        project = project_cls()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        return project, await project.grpc.servers.default

    async def connect(self, server: DefaultGrpcServer) -> aio.Channel:
        [address] = server.addresses
        channel = aio.insecure_channel(address)
        self.addAsyncCleanup(channel.close)
        return channel

    async def test_every_kind_of_rpc_is_served(self) -> None:
        _, server = await self.start()
        echo = tst_pb2_grpc.EchoStub(await self.connect(server))
        reply = await echo.Unary(EchoRequest(text="a"))
        self.assertEqual(reply.text, "a")
        reply = await echo.ClientStream(requests("a", "b"))
        self.assertEqual(reply.text, "a.b")
        replies = [r.text async for r in echo.ServerStream(EchoRequest(text="a.b"))]
        self.assertEqual(replies, ["a", "b"])
        replies = [r.text async for r in echo.BidiStream(requests("a", "b"))]
        self.assertEqual(replies, ["A", "B"])

    async def test_every_service_of_the_api_is_served(self) -> None:
        _, server = await self.start()
        ping = tst_pb2_grpc.PingStub(await self.connect(server))
        self.assertEqual((await ping.Ping(EchoRequest())).text, "pong")

    async def test_the_server_tells_its_addresses(self) -> None:
        _, server = await self.start()
        [address] = server.addresses
        host, port = address.rsplit(":", 1)
        self.assertEqual(host, "127.0.0.1")
        self.assertGreater(int(port), 0)
        self.assertEqual(repr(server), f"<DefaultGrpcServer {address}>")

    async def test_a_server_without_services_warns(self) -> None:
        with self.assertLogs("ingot_grpcio", "WARNING") as logs:
            _, server = await self.start(GrpcProject)
        [address] = server.addresses
        self.assertEqual(
            logs.output,
            [
                f"WARNING:ingot_grpcio.grpc.servers.base:<DefaultGrpcServer "
                f"{address}>: serving nothing: its binding gives no services"
            ],
        )
        self.assertTrue(server.addresses)

    async def test_the_shutdown_lets_the_calls_in_progress_finish(self) -> None:
        project, server = await self.start()
        echo = tst_pb2_grpc.EchoStub(await self.connect(server))
        call = asyncio.ensure_future(echo.Unary(EchoRequest(text="slow")))
        await asyncio.sleep(0.05)
        await project._do_shut_down()
        self.assertEqual((await call).text, "slow")
        with self.assertRaises(aio.AioRpcError) as raised:
            await echo.Unary(EchoRequest(text="late"))
        self.assertEqual(raised.exception.code(), grpc.StatusCode.UNAVAILABLE)

    async def test_the_configs_reach_the_server(self) -> None:
        os.environ.update(
            {
                "INGOT_GRPC_DEFAULT_MAX_CONCURRENT_RPCS": "0",
                "INGOT_GRPC_DEFAULT_SHUTDOWN_GRACE": "1.5",
            }
        )
        project = TstProject()
        await project._configure()
        server = project.grpc.servers.default
        self.assertEqual(server._get_listen_hosts(), ("127.0.0.1",))
        self.assertEqual(server._get_port(), 0)
        self.assertIsNone(server._get_max_concurrent_rpcs())
        self.assertEqual(server._get_shutdown_grace(), 1.5)


class ComponentTestCase(unittest.TestCase):
    def test_the_server_is_a_component_of_the_project(self) -> None:
        argv = ["--config", "IS_PRINT_CONFIGS=off", "components", "list"]
        with (
            mock.patch.dict(os.environ, clear=True),
            mock.patch("logging.config.dictConfig"),
            contextlib.redirect_stdout(io.StringIO()) as out,
        ):
            code = CommandRunner(TstProject, argv).run()
        self.assertEqual(code, 0)
        self.assertIn(
            "grpc.servers.default: DefaultGrpcServer, shutdown order 2\n",
            out.getvalue(),
        )


class PingOnlyGrpcBinding(AutoGrpcBinding):
    project: "TstProject"

    @t.override
    def _iter_services(self) -> t.Iterator[GrpcService]:
        yield self.project.grpc.api.ping


class BindingTestCase(ServerTestCase):
    def make_project(self, binding: type[AutoGrpcBinding]) -> type[TstProject]:
        class Bindings(GrpcBindings):
            default = Slot(binding)

        class Unit(TstGrpcUnit):
            bindings = Slot(Bindings)

        class Project(TstProject):
            grpc = Slot(Unit)

        return Project

    async def test_the_binding_chooses_the_services_of_the_server(self) -> None:
        _, server = await self.start(self.make_project(PingOnlyGrpcBinding))
        channel = await self.connect(server)
        ping = tst_pb2_grpc.PingStub(channel)
        self.assertEqual((await ping.Ping(EchoRequest())).text, "pong")
        with self.assertRaises(aio.AioRpcError) as raised:
            await tst_pb2_grpc.EchoStub(channel).Unary(EchoRequest(text="a"))
        self.assertEqual(raised.exception.code(), grpc.StatusCode.UNIMPLEMENTED)

    async def test_the_auto_binding_skips_a_service_with_no_servicer(self) -> None:
        class ContractOnly(GrpcService, full_name="tst.Echo", module=tst_pb2_grpc):
            pass

        class Api(GrpcApi):
            echo = Slot(ContractOnly)
            ping = Slot(PingService)

        class Unit(GrpcUnit):
            api = Slot(Api)

        class Project(GrpcProject):
            grpc = Slot(Unit)

        project, _ = await self.start(Project)
        services = list(project.grpc.bindings.default.iter_services())
        self.assertEqual([s.FULL_NAME for s in services], ["tst.Ping"])

    async def test_a_binding_serves_only_what_is_implemented(self) -> None:
        class ContractOnly(GrpcService, full_name="tst.Echo", module=tst_pb2_grpc):
            pass

        class Bad(AutoGrpcBinding):
            @t.override
            def _iter_services(self) -> t.Iterator[GrpcService]:
                yield ContractOnly(self.project)

        with self.assertRaisesRegex(
            TypeError,
            r"^<\S*Bad>: <\S*ContractOnly tst.Echo> has no SERVICER to serve$",
        ):
            await self.start(self.make_project(Bad))

    async def test_a_binding_gives_a_service_once(self) -> None:
        class Twice(AutoGrpcBinding):
            project: "TstProject"

            @t.override
            def _iter_services(self) -> t.Iterator[GrpcService]:
                yield self.project.grpc.api.ping
                yield self.project.grpc.api.ping

        with self.assertRaisesRegex(
            TypeError, r"^<\S*Twice>: 'tst.Ping' is given twice$"
        ):
            await self.start(self.make_project(Twice))


class ServiceTestCase(unittest.TestCase):
    @t.override
    def setUp(self) -> None:
        self.enterContext(mock.patch.dict(os.environ, clear=True))

    def test_the_generated_code_is_found_by_its_names(self) -> None:
        self.assertIs(EchoService.SERVICER_BASE, tst_pb2_grpc.EchoServicer)
        self.assertIs(EchoService.STUB, tst_pb2_grpc.EchoStub)
        self.assertEqual(
            [method.name for method in EchoService.DESCRIPTOR.methods],
            ["Unary", "ClientStream", "ServerStream", "BidiStream"],
        )
        self.assertEqual(EchoService.DESCRIPTOR.file.name, "tests/proto/tst.proto")

    def test_a_contract_needs_no_servicer(self) -> None:
        class ContractOnly(GrpcService, full_name="tst.Echo", module=tst_pb2_grpc):
            pass

        self.assertIs(ContractOnly.STUB, tst_pb2_grpc.EchoStub)
        project = TstProject()
        with self.assertRaisesRegex(
            LookupError, r"ContractOnly tst.Echo> has no SERVICER: nothing implements"
        ):
            ContractOnly(project).servicer

    def test_an_unknown_service_fails(self) -> None:
        with self.assertRaisesRegex(
            LookupError, r"Bad: no gRPC service 'tst.Nothing': import its"
        ):

            class Bad(GrpcService, full_name="tst.Nothing", module=tst_pb2_grpc):
                pass

    def test_a_module_of_another_service_fails(self) -> None:
        from .proto import tst_pb2

        with self.assertRaisesRegex(
            LookupError,
            r"Bad: tests.proto.tst_pb2 is not the _pb2_grpc module of 'tst.Echo': "
            r"no EchoServicer, EchoStub, add_EchoServicer_to_server$",
        ):

            class Bad(GrpcService, full_name="tst.Echo", module=tst_pb2):
                pass

    def test_the_name_and_the_module_go_together(self) -> None:
        with self.assertRaisesRegex(
            TypeError, r"Bad: full_name and module go together$"
        ):

            class Bad(GrpcService, full_name="tst.Echo"):
                pass

    def test_the_servicer_is_created_once_with_the_project(self) -> None:
        project = TstProject()
        service = project.grpc.api.echo
        self.assertIsInstance(service.servicer, Echo)
        self.assertIs(service.servicer, service.servicer)
        self.assertIs(service.servicer.project, project)
        self.assertEqual(repr(service), "<EchoService tst.Echo>")

    def test_a_subclass_replaces_the_implementation(self) -> None:
        class AppEcho(Echo):
            pass

        class AppEchoService(EchoService):
            SERVICER = AppEcho

        class Api(TstGrpcApi):
            echo = Slot(AppEchoService)

        project = TstProject()
        self.assertIsInstance(Api(project).echo.servicer, AppEcho)
        self.assertIs(AppEchoService.DESCRIPTOR, EchoService.DESCRIPTOR)

    def test_another_implementation_extends_the_contract(self) -> None:
        class EchoContract(GrpcService, full_name="tst.Echo", module=tst_pb2_grpc):
            pass

        class LoudEcho(GrpcServicer, tst_pb2_grpc.EchoServicer):
            pass

        class QuietEchoService(EchoContract):
            SERVICER = Echo

        class LoudEchoService(EchoContract):
            SERVICER = LoudEcho

        self.assertIs(LoudEchoService.STUB, QuietEchoService.STUB)
        project = TstProject()
        self.assertIsInstance(LoudEchoService(project).servicer, LoudEcho)

    def test_a_service_without_a_name_is_a_base(self) -> None:
        class AppService(GrpcService):
            pass

        class AppEchoService(AppService, full_name="tst.Echo", module=tst_pb2_grpc):
            SERVICER = Echo

        project = TstProject()
        self.assertRegex(repr(AppService(project)), r"^<\S*AppService ->$")
        self.assertIs(AppEchoService.STUB, tst_pb2_grpc.EchoStub)

    def test_the_servicer_extends_the_base_of_the_service(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            r"Bad.SERVICER: Ping does not extend EchoServicer, the servicer base of",
        ):

            class Bad(EchoService):
                SERVICER = Ping  # type: ignore[assignment]

    def test_the_servicer_is_a_servicer(self) -> None:
        with self.assertRaisesRegex(TypeError, r"Bad.SERVICER: .*EchoServicer'> is no"):

            class Bad(EchoService):
                SERVICER = tst_pb2_grpc.EchoServicer  # type: ignore[assignment]

    def test_a_servicer_needs_a_service(self) -> None:
        with self.assertRaisesRegex(TypeError, r"Bad: a SERVICER of no service$"):

            class Bad(GrpcService):
                SERVICER = Echo


class ApiTestCase(unittest.TestCase):
    def test_a_service_is_in_the_api_once(self) -> None:
        class OtherEchoService(EchoService):
            pass

        with self.assertRaisesRegex(
            TypeError, r"BadGrpcApi: 'tst.Echo' is in both echo and other$"
        ):

            class BadGrpcApi(GrpcApi):
                echo = Slot(EchoService)
                other = Slot(OtherEchoService)

    def test_a_service_in_the_api_declares_its_name(self) -> None:
        class AppService(GrpcService):
            pass

        with self.assertRaisesRegex(
            TypeError, r"BadGrpcApi.app: .*AppService declares no FULL_NAME$"
        ):

            class BadGrpcApi(GrpcApi):
                app = Slot(AppService)
