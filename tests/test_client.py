import os
import socket
import typing as t
import unittest
from collections.abc import AsyncIterator, Iterator
from unittest import mock

import grpc
from grpc import aio

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.clients import DefaultGrpcClient, GrpcClients
from ingot_grpcio.grpc.errors import GrpcError, GrpcErrors
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServers
from ingot_grpcio.grpc.services import GrpcService, GrpcServicer
from ingots.puer import Slot

from .proto import tst_pb2_grpc
from .proto.tst_pb2 import EchoReply, EchoRequest
from .test_errors import InsufficientFunds, InsufficientFundsPolicy

Context: t.TypeAlias = aio.ServicerContext[EchoRequest, EchoReply]


def answer(text: str) -> EchoReply:
    if text == "funds":
        raise InsufficientFunds.for_account("acc-1")
    return EchoReply(text=text)


class Echo(GrpcServicer, tst_pb2_grpc.EchoServicer):
    @t.override
    async def Unary(self, request: EchoRequest, context: Context) -> EchoReply:
        context.set_trailing_metadata((("served-by", "echo"),))
        return answer(request.text)

    @t.override
    async def ClientStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> EchoReply:
        return answer(".".join([r.text async for r in request_iterator]))

    @t.override
    async def ServerStream(
        self, request: EchoRequest, context: Context
    ) -> AsyncIterator[EchoReply]:
        for text in request.text.split("."):
            yield answer(text)

    @t.override
    async def BidiStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> AsyncIterator[EchoReply]:
        async for request in request_iterator:
            yield answer(request.text)


class TstGrpcBinding:
    echo = GrpcService(tst_pb2_grpc.EchoStub, Echo)


class TstGrpcServer(TstGrpcBinding, DefaultGrpcServer):
    pass


class TstGrpcClient(TstGrpcBinding, DefaultGrpcClient):
    # a contract alone: the server does not serve it
    ping = GrpcService(tst_pb2_grpc.PingStub)


class TstGrpcErrors(GrpcErrors):
    insufficient_funds = Slot(InsufficientFundsPolicy)


class TstGrpcServers(GrpcServers):
    default = Slot(TstGrpcServer)


class TstGrpcClients(GrpcClients):
    default = Slot(TstGrpcClient)


class TstGrpcUnit(GrpcUnit):
    errors = Slot(TstGrpcErrors)
    servers = Slot(TstGrpcServers)
    clients = Slot(TstGrpcClients)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


class RecordingInterceptor(aio.UnaryUnaryClientInterceptor):
    def __init__(self) -> None:
        self.codes: list[grpc.StatusCode] = []

    @t.override
    async def intercept_unary_unary(
        self,
        continuation: t.Callable[
            [aio.ClientCallDetails, t.Any],
            t.Awaitable[aio.UnaryUnaryCall[t.Any, t.Any]],
        ],
        client_call_details: aio.ClientCallDetails,
        request: t.Any,
    ) -> aio.UnaryUnaryCall[t.Any, t.Any]:
        call = await continuation(client_call_details, request)
        self.codes.append(await call.code())
        return call


RECORDING = RecordingInterceptor()


class RecordingGrpcClient(TstGrpcClient):
    @t.override
    def _iter_interceptors(self) -> Iterator[aio.ClientInterceptor]:
        yield from super()._iter_interceptors()
        yield RECORDING


class RecordingGrpcClients(TstGrpcClients):
    default = Slot(RecordingGrpcClient)


class RecordingGrpcUnit(TstGrpcUnit):
    clients = Slot(RecordingGrpcClients)


class RecordingProject(TstProject):
    grpc = Slot(RecordingGrpcUnit)


def find_free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return t.cast(int, sock.getsockname()[1])


async def requests(*texts: str) -> AsyncIterator[EchoRequest]:
    for text in texts:
        yield EchoRequest(text=text)


class ClientTestCase(unittest.IsolatedAsyncioTestCase):
    @t.override
    async def asyncSetUp(self) -> None:
        # the client finds the server on the port of its configs: a free one
        self.enterContext(
            mock.patch.dict(
                os.environ,
                {
                    "INGOT_GRPC_DEFAULT_LISTEN_HOST": "127.0.0.1",
                    "INGOT_GRPC_DEFAULT_HOST": "127.0.0.1",
                    "INGOT_GRPC_DEFAULT_PORT": str(find_free_port()),
                    "INGOT_IS_PRINT_CONFIGS": "off",
                },
                clear=True,
            )
        )
        # the logging is not under test: keep the handlers of the test run
        self.enterContext(mock.patch("logging.config.dictConfig"))

    async def start(
        self, project_cls: type[TstProject] = TstProject, *, is_serving: bool = True
    ) -> tuple[TstProject, TstGrpcClient]:
        project = project_cls()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        if is_serving:
            await project.grpc.servers.default
        with self.assertLogs("ingot_grpcio", "INFO"):
            client = await project.grpc.clients.default
        return project, client

    async def test_a_client_calls_the_default_server(self) -> None:
        _, client = await self.start()
        echo = client.echo
        self.assertEqual((await echo.Unary(EchoRequest(text="a"))).text, "a")
        reply = await echo.ClientStream(requests("a", "b"))
        self.assertEqual(reply.text, "a.b")
        replies = [r.text async for r in echo.ServerStream(EchoRequest(text="a.b"))]
        self.assertEqual(replies, ["a", "b"])
        replies = [r.text async for r in echo.BidiStream(requests("a", "b"))]
        self.assertEqual(replies, ["a", "b"])

    async def test_a_call_stays_a_call(self) -> None:
        _, client = await self.start()
        call = client.echo.Unary(EchoRequest(text="a"))
        await call
        self.assertEqual(await call.code(), grpc.StatusCode.OK)
        self.assertIn(("served-by", "echo"), list(await call.trailing_metadata()))

    async def test_a_failed_call_raises_a_grpc_error(self) -> None:
        _, client = await self.start()
        echo = client.echo
        with (
            self.assertLogs("ingot_grpcio", "DEBUG") as logs,
            self.assertRaises(GrpcError) as raised,
        ):
            await echo.Unary(EchoRequest(text="funds"))
        error = raised.exception
        self.assertEqual(error.code, grpc.StatusCode.FAILED_PRECONDITION)
        self.assertEqual(
            (error.domain, error.reason, error.metadata),
            ("shop.example.com", "INSUFFICIENT_FUNDS", {"account": "acc-1"}),
        )
        self.assertIsInstance(error.__cause__, aio.AioRpcError)
        self.assertIn(
            "DEBUG:ingot_grpcio.grpc.errors.client_handler:/tst.Echo/Unary: "
            "FAILED_PRECONDITION 'insufficient funds on acc-1', "
            "shop.example.com/INSUFFICIENT_FUNDS",
            logs.output,
        )

    async def test_every_kind_of_rpc_raises_a_grpc_error(self) -> None:
        _, client = await self.start()
        echo = client.echo
        with self.assertRaises(GrpcError) as raised:
            await echo.ClientStream(requests("funds"))
        self.assertEqual(raised.exception.reason, "INSUFFICIENT_FUNDS")
        replies = []
        with self.assertRaises(GrpcError) as raised:
            async for reply in echo.ServerStream(EchoRequest(text="a.funds")):
                replies.append(reply.text)
        self.assertEqual(replies, ["a"])
        self.assertEqual(raised.exception.reason, "INSUFFICIENT_FUNDS")
        call = echo.ServerStream(EchoRequest(text="a.funds"))
        self.assertEqual(t.cast(EchoReply, await call.read()).text, "a")
        with self.assertRaises(GrpcError):
            await call.read()

    async def test_a_stream_is_written_and_read(self) -> None:
        _, client = await self.start()
        bidi = client.echo.BidiStream()
        await bidi.write(EchoRequest(text="a"))
        self.assertEqual(t.cast(EchoReply, await bidi.read()).text, "a")
        await bidi.write(EchoRequest(text="funds"))
        with self.assertRaises(GrpcError) as raised:
            await bidi.read()
        self.assertEqual(raised.exception.reason, "INSUFFICIENT_FUNDS")
        self.assertEqual(await bidi.code(), grpc.StatusCode.FAILED_PRECONDITION)

    async def test_a_call_reaching_no_server_raises_a_grpc_error(self) -> None:
        _, client = await self.start(is_serving=False)
        echo = client.echo
        with self.assertRaises(GrpcError) as raised:
            await echo.Unary(EchoRequest(text="a"), timeout=5)
        error = raised.exception
        self.assertEqual(error.code, grpc.StatusCode.UNAVAILABLE)
        self.assertEqual((error.domain, error.reason), ("", ""))

    async def test_a_stub_is_created_once_on_the_channel(self) -> None:
        project, client = await self.start()
        self.assertIsInstance(client.echo, tst_pb2_grpc.EchoStub)
        self.assertIs(client.echo, client.echo)
        other = TstGrpcClient(project)
        await other
        self.assertIsNot(other.echo, client.echo)

    async def test_a_service_the_server_does_not_serve_is_unimplemented(self) -> None:
        _, client = await self.start()
        with self.assertRaises(GrpcError) as raised:
            await client.ping.Ping(EchoRequest())
        self.assertEqual(raised.exception.code, grpc.StatusCode.UNIMPLEMENTED)

    async def test_a_stub_needs_a_configured_client(self) -> None:
        project = TstProject()
        with self.assertRaisesRegex(
            RuntimeError, r"^<TstGrpcClient -> is not configured: await it before"
        ):
            project.grpc.clients.default.echo

    async def test_the_client_logs_its_lifecycle(self) -> None:
        project = TstProject()
        await project._configure()
        client = project.grpc.clients.default
        self.assertEqual(repr(client), "<TstGrpcClient ->")
        with self.assertLogs("ingot_grpcio", "INFO") as logs:
            await client
        target = os.environ["INGOT_GRPC_DEFAULT_PORT"]
        self.assertEqual(repr(client), f"<TstGrpcClient 127.0.0.1:{target}>")
        self.assertIn(f"{client!r}: calling tst.Ping, tst.Echo", logs.output[0])
        with self.assertLogs("ingot_grpcio", "INFO") as logs:
            await project._do_shut_down()
        self.assertIn(f"{client!r}: closed", logs.output[-1])

    async def test_a_client_of_no_services_warns(self) -> None:
        project = GrpcProject()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        with self.assertLogs("ingot_grpcio", "WARNING") as logs:
            client = await project.grpc.clients.default
        self.assertIn(f"{client!r}: calling nothing", logs.output[0])

    async def test_a_client_adds_interceptors_of_its_own(self) -> None:
        _, client = await self.start(RecordingProject)
        echo = client.echo
        await echo.Unary(EchoRequest(text="a"))
        with self.assertRaises(GrpcError):
            await echo.Unary(EchoRequest(text="funds"))
        self.assertEqual(
            RECORDING.codes, [grpc.StatusCode.OK, grpc.StatusCode.FAILED_PRECONDITION]
        )
