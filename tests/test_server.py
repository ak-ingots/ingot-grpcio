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
from ingot_grpcio.grpc.clients import DefaultGrpcClient
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServers
from ingot_grpcio.grpc.services import GrpcService, GrpcServicer
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


class TstGrpcBinding:
    echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)
    ping = GrpcService(tst_pb2_grpc.PingStub, Ping)


class TstGrpcServer(TstGrpcBinding, DefaultGrpcServer):
    pass


class TstGrpcServers(GrpcServers):
    default = Slot(TstGrpcServer)


class TstGrpcUnit(GrpcUnit):
    servers = Slot(TstGrpcServers)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


def make_project(server_cls: type[DefaultGrpcServer]) -> type[GrpcProject]:
    class Servers(GrpcServers):
        default = Slot(server_cls)

    class Unit(GrpcUnit):
        servers = Slot(Servers)

    class Project(GrpcProject):
        grpc = Slot(Unit)

    return Project


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

    async def test_every_service_of_the_bindings_is_served(self) -> None:
        _, server = await self.start()
        ping = tst_pb2_grpc.PingStub(await self.connect(server))
        self.assertEqual((await ping.Ping(EchoRequest())).text, "pong")

    async def test_a_server_serves_only_its_bindings(self) -> None:
        class PingOnlyBinding:
            ping = GrpcService(tst_pb2_grpc.PingStub, Ping)

        class PingOnlyServer(PingOnlyBinding, DefaultGrpcServer):
            pass

        _, server = await self.start(make_project(PingOnlyServer))
        channel = await self.connect(server)
        ping = tst_pb2_grpc.PingStub(channel)
        self.assertEqual((await ping.Ping(EchoRequest())).text, "pong")
        with self.assertRaises(aio.AioRpcError) as raised:
            await tst_pb2_grpc.EchoStub(channel).Unary(EchoRequest(text="a"))
        self.assertEqual(raised.exception.code(), grpc.StatusCode.UNIMPLEMENTED)

    async def test_the_servicer_is_created_once_with_the_project(self) -> None:
        project, server = await self.start()
        servicer = t.cast(TstGrpcServer, server).echo
        self.assertIsInstance(servicer, Echo)
        self.assertIs(t.cast(TstGrpcServer, server).echo, servicer)
        self.assertIs(servicer.project, project)

    async def test_the_server_tells_its_addresses(self) -> None:
        _, server = await self.start()
        [address] = server.addresses
        host, port = address.rsplit(":", 1)
        self.assertEqual(host, "127.0.0.1")
        self.assertGreater(int(port), 0)
        self.assertEqual(repr(server), f"<TstGrpcServer {address}>")

    async def test_a_server_without_services_warns(self) -> None:
        with self.assertLogs("ingot_grpcio", "WARNING") as logs:
            _, server = await self.start(GrpcProject)
        [address] = server.addresses
        self.assertEqual(
            logs.output,
            [
                f"WARNING:ingot_grpcio.grpc.servers.base:<DefaultGrpcServer "
                f"{address}>: serving nothing: it extends no binding"
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
            "grpc.servers.default: TstGrpcServer, shutdown order 2\n",
            out.getvalue(),
        )


class ServiceTestCase(unittest.TestCase):
    def test_the_generated_code_is_found_by_the_stub(self) -> None:
        service = TstGrpcBinding.echo
        self.assertEqual((service.name, service.full_name), ("echo", "tst.Echo"))
        self.assertIs(service.servicer_base, tst_pb2_grpc.EchoServicer)
        self.assertIs(service.servicer_cls, Echo)
        self.assertEqual(
            [method.name for method in service.descriptor.methods],
            ["Unary", "ClientStream", "ServerStream", "BidiStream"],
        )
        self.assertEqual(service.descriptor.file.name, "tests/proto/tst.proto")
        self.assertEqual(repr(service), "<GrpcService tst.Echo>")

    def test_a_contract_needs_no_servicer(self) -> None:
        contract = GrpcService(tst_pb2_grpc.EchoStub)
        self.assertIsNone(contract.servicer_cls)
        with mock.patch.dict(os.environ, clear=True):
            project = TstProject()
        with self.assertRaisesRegex(
            LookupError, r"^<GrpcService tst.Echo> has no servicer: nothing"
        ):
            contract.build_servicer(project)

    def test_a_server_refuses_a_contract(self) -> None:
        with self.assertRaisesRegex(
            TypeError, r"\bBad.echo: <GrpcService tst.Echo> has no servicer to serve$"
        ):

            class Bad(DefaultGrpcServer):
                echo = GrpcService(tst_pb2_grpc.EchoStub)

    def test_a_stub_is_one_grpcio_generates(self) -> None:
        for stub in (EchoRequest, tst_pb2_grpc.EchoServicer, lambda channel: None):
            with (
                self.subTest(stub),
                self.assertRaisesRegex(
                    LookupError, r"is not a stub that grpcio generates$"
                ),
            ):
                GrpcService(stub)  # type: ignore[arg-type]

    def test_the_servicer_extends_the_base_of_the_service(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            r"^<GrpcService tst.Echo>: the servicer Ping does not extend "
            r"EchoServicer$",
        ):
            GrpcService(tst_pb2_grpc.EchoStub, Ping)

    def test_the_servicer_is_a_servicer(self) -> None:
        with self.assertRaisesRegex(
            TypeError, r"the servicer <class .*EchoServicer'> is no GrpcServicer$"
        ):
            GrpcService(
                tst_pb2_grpc.EchoStub, tst_pb2_grpc.EchoServicer  # type: ignore
            )

    def test_a_service_keeps_its_name(self) -> None:
        service = GrpcService(tst_pb2_grpc.EchoStub, Echo)
        with self.assertRaisesRegex(
            TypeError, r"Bad.other: <GrpcService tst.Echo> is already echo$"
        ):

            class Bad:
                echo = service
                other = service


class OwnerTestCase(unittest.TestCase):
    def test_the_services_come_from_the_bindings_in_order(self) -> None:
        class EchoBinding:
            echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)

        class PingBinding:
            ping = GrpcService(tst_pb2_grpc.PingStub, Ping)

        class PingEchoServer(PingBinding, EchoBinding, DefaultGrpcServer):
            pass

        names = [s.name for s in PingEchoServer.grpc_services_iter()]
        self.assertEqual(names, ["ping", "echo"])
        names = [s.name for s in TstGrpcServer.grpc_services_iter()]
        self.assertEqual(names, ["echo", "ping"])

    def test_a_subclass_refines_the_servicer(self) -> None:
        class LoudEcho(Echo):
            pass

        class LoudServer(TstGrpcServer):
            echo = GrpcService(tst_pb2_grpc.EchoStub, LoudEcho)

        self.assertIs(LoudServer.echo.servicer_cls, LoudEcho)
        services = list(LoudServer.grpc_services_iter())
        self.assertEqual([s.name for s in services], ["echo", "ping"])

    def test_a_subclass_drops_a_service(self) -> None:
        class EchoOnlyServer(TstGrpcServer):
            ping = None  # type: ignore[assignment]

        names = [service.name for service in EchoOnlyServer.grpc_services_iter()]
        self.assertEqual(names, ["echo"])

    def test_a_replacement_implements_a_contract(self) -> None:
        class ContractBinding:
            echo = GrpcService(tst_pb2_grpc.EchoStub)

        class EchoServer(ContractBinding, DefaultGrpcServer):
            echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)  # type: ignore

        self.assertIs(EchoServer.echo.servicer_cls, Echo)

    def test_an_attribute_of_a_base_does_not_hide_a_service(self) -> None:
        class Holder:
            echo = None

        class EchoServer(TstGrpcBinding, Holder, DefaultGrpcServer):  # type: ignore
            pass

        names = [service.name for service in EchoServer.grpc_services_iter()]
        self.assertEqual(names, ["echo", "ping"])

    def test_a_replacement_keeps_the_contract(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            r"\bBad.echo: <GrpcService tst.Ping> replaces another service, "
            r"<GrpcService tst.Echo>$",
        ):

            class Bad(TstGrpcServer):
                echo = GrpcService(tst_pb2_grpc.PingStub, Ping)  # type: ignore

    def test_a_replacement_extends_the_servicer(self) -> None:
        class OtherEcho(GrpcServicer, tst_pb2_grpc.EchoServicer):
            pass

        with self.assertRaisesRegex(
            TypeError, r"\bBad.echo: the servicer \S*OtherEcho does not extend Echo$"
        ):

            class Bad(TstGrpcServer):
                # mypy sees it too: the servicer is no Echo
                echo = GrpcService(
                    tst_pb2_grpc.EchoStub, OtherEcho  # type: ignore[type-abstract]
                )  # type: ignore[assignment]

    def test_a_replacement_keeps_the_servicer(self) -> None:
        class Client(TstGrpcBinding, DefaultGrpcClient):
            pass

        with self.assertRaisesRegex(
            TypeError, r"\bBad.echo: the servicer None does not extend Echo$"
        ):

            class Bad(Client):
                echo = GrpcService(tst_pb2_grpc.EchoStub)

    def test_a_service_is_given_once(self) -> None:
        with self.assertRaisesRegex(
            TypeError, r"\bBad: 'tst.Echo' is in both other and echo$"
        ):

            class Bad(TstGrpcServer):
                other = GrpcService(tst_pb2_grpc.EchoStub, Echo)
