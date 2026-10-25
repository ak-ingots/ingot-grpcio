import logging
import os
import pickle
import typing as t
import unittest
from collections.abc import AsyncIterator, Iterator
from unittest import mock

import grpc
from google.protobuf import any_pb2
from google.protobuf.message import Message
from google.rpc import error_details_pb2, status_pb2
from grpc import aio

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.errors import (
    BaseGrpcErrorPolicy,
    BaseStaticGrpcErrorPolicy,
    GrpcError,
    GrpcErrors,
    InternalGrpcErrorPolicy,
)
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServers
from ingot_grpcio.grpc.services import GrpcService, GrpcServicer
from ingots.puer import Slot

from .proto import tst_pb2_grpc
from .proto.tst_pb2 import EchoReply, EchoRequest

Context: t.TypeAlias = aio.ServicerContext[EchoRequest, EchoReply]


class ShopError(Exception):
    """A business error, by the pattern of ingots: args, then creators."""

    @classmethod
    def build(cls, message: str) -> t.Self:
        return cls(message)

    @t.override
    def __str__(self) -> str:
        return t.cast(str, self.args[0])


class InsufficientFunds(ShopError):
    @classmethod
    def for_account(cls, account: str) -> t.Self:
        return cls(f"insufficient funds on {account}", account)

    @property
    def account(self) -> str:
        return t.cast(str, self.args[1])


class OutOfStock(ShopError):
    pass


class ShopErrorPolicy(BaseStaticGrpcErrorPolicy):
    EXCEPTION = ShopError
    CODE = grpc.StatusCode.FAILED_PRECONDITION
    DOMAIN = "shop.example.com"
    REASON = "SHOP"


class InsufficientFundsPolicy(BaseStaticGrpcErrorPolicy):
    EXCEPTION = InsufficientFunds
    CODE = grpc.StatusCode.FAILED_PRECONDITION
    DOMAIN = "shop.example.com"
    REASON = "INSUFFICIENT_FUNDS"

    @t.override
    def _get_metadata(self, error: Exception) -> dict[str, str]:
        assert isinstance(error, InsufficientFunds)
        return {"account": error.account}

    @t.override
    def _iter_details(self, error: Exception) -> Iterator[Message]:
        violation = error_details_pb2.PreconditionFailure.Violation(
            type="FUNDS", subject="acc-1", description="top it up"
        )
        yield error_details_pb2.PreconditionFailure(violations=[violation])


async def fail(text: str, context: Context) -> None:
    match text:
        case "funds":
            raise InsufficientFunds.for_account("acc-1")
        case "stock":
            raise OutOfStock.build("out of stock")
        case "abort":
            await context.abort(grpc.StatusCode.NOT_FOUND, "gone")
        case _:
            raise RuntimeError("the secret of the server")


class FailingEcho(GrpcServicer, tst_pb2_grpc.EchoServicer):
    @t.override
    async def Unary(self, request: EchoRequest, context: Context) -> EchoReply:
        await fail(request.text, context)
        return EchoReply()  # pragma: no cover

    @t.override
    async def ClientStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> EchoReply:
        async for request in request_iterator:
            await fail(request.text, context)
        return EchoReply()  # pragma: no cover

    @t.override
    async def ServerStream(
        self, request: EchoRequest, context: Context
    ) -> AsyncIterator[EchoReply]:
        yield EchoReply(text="first")
        await fail(request.text, context)

    @t.override
    async def BidiStream(
        self, request_iterator: AsyncIterator[EchoRequest], context: Context
    ) -> AsyncIterator[EchoReply]:
        async for request in request_iterator:
            yield EchoReply(text="first")
            await fail(request.text, context)


class FailingGrpcBinding:
    echo = GrpcService(tst_pb2_grpc.EchoStub, FailingEcho)


class FailingGrpcServer(FailingGrpcBinding, DefaultGrpcServer):
    pass


class TstGrpcServers(GrpcServers):
    default = Slot(FailingGrpcServer)


class TstGrpcErrors(GrpcErrors):
    shop = Slot(ShopErrorPolicy)
    insufficient_funds = Slot(InsufficientFundsPolicy)


class TstGrpcUnit(GrpcUnit):
    errors = Slot(TstGrpcErrors)
    servers = Slot(TstGrpcServers)


class TstProject(GrpcProject):
    grpc = Slot(TstGrpcUnit)


async def read(
    call: aio.UnaryStreamCall[t.Any, t.Any] | aio.StreamStreamCall[t.Any, t.Any],
) -> EchoReply:
    reply = await call.read()
    assert isinstance(reply, EchoReply)
    return reply


async def requests(*texts: str) -> AsyncIterator[EchoRequest]:
    for text in texts:
        yield EchoRequest(text=text)


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

    async def start(self) -> tuple[TstProject, tst_pb2_grpc.EchoAsyncStub]:
        project = TstProject()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        server: DefaultGrpcServer = await project.grpc.servers.default
        [address] = server.addresses
        channel = aio.insecure_channel(address)
        self.addAsyncCleanup(channel.close)
        return project, tst_pb2_grpc.EchoStub(channel)

    async def call(
        self, stub: tst_pb2_grpc.EchoAsyncStub, text: str
    ) -> aio.AioRpcError:
        with self.assertRaises(aio.AioRpcError) as raised:
            await stub.Unary(EchoRequest(text=text))
        return raised.exception

    async def decode(self, project: TstProject, error: aio.AioRpcError) -> GrpcError:
        return project.grpc.errors.client_handler.decode_rpc_error(error)


class ServerTestCase(ServerFixture):
    async def test_a_coded_exception_reaches_the_client_as_itself(self) -> None:
        project, stub = await self.start()
        with self.assertLogs("ingot_grpcio", "INFO") as logs:
            error = await self.call(stub, "funds")
        self.assertEqual(error.code(), grpc.StatusCode.FAILED_PRECONDITION)
        self.assertEqual(error.details(), "insufficient funds on acc-1")
        self.assertIn(
            "/tst.Echo/Unary: InsufficientFunds('insufficient funds on acc-1', "
            "'acc-1'), shop.example.com/INSUFFICIENT_FUNDS",
            logs.output[-1],
        )
        decoded = await self.decode(project, error)
        self.assertEqual(decoded.code, grpc.StatusCode.FAILED_PRECONDITION)
        self.assertEqual(decoded.message, "insufficient funds on acc-1")
        self.assertEqual(
            (decoded.domain, decoded.reason, decoded.metadata),
            ("shop.example.com", "INSUFFICIENT_FUNDS", {"account": "acc-1"}),
        )
        failure = decoded.find_detail(error_details_pb2.PreconditionFailure)
        assert failure is not None
        self.assertEqual(failure.violations[0].type, "FUNDS")

    async def test_an_exception_takes_the_policy_of_its_nearest_base(self) -> None:
        project, stub = await self.start()
        decoded = await self.decode(project, await self.call(stub, "stock"))
        self.assertEqual((decoded.reason, decoded.message), ("SHOP", "out of stock"))

    async def test_an_unexpected_exception_tells_nothing(self) -> None:
        project, stub = await self.start()
        with self.assertLogs("ingot_grpcio", "ERROR") as logs:
            error = await self.call(stub, "boom")
        self.assertEqual(error.code(), grpc.StatusCode.INTERNAL)
        self.assertEqual(error.details(), "internal error")
        self.assertIn("RuntimeError('the secret of the server')", logs.output[0])
        self.assertIn("Traceback", logs.output[0])
        decoded = await self.decode(project, error)
        self.assertEqual((decoded.domain, decoded.reason), ("ingot_grpcio", "INTERNAL"))
        self.assertIsNone(decoded.find_detail(error_details_pb2.DebugInfo))

    async def test_the_debug_info_tells_the_traceback(self) -> None:
        os.environ["INGOT_GRPC_DEFAULT_IS_SEND_DEBUG_INFO"] = "on"
        project, stub = await self.start()
        with self.assertLogs("ingot_grpcio", "ERROR"):
            decoded = await self.decode(project, await self.call(stub, "boom"))
        debug_info = decoded.find_detail(error_details_pb2.DebugInfo)
        assert debug_info is not None
        self.assertEqual(debug_info.detail, "RuntimeError: the secret of the server")
        self.assertIn("in fail", debug_info.stack_entries[-1])

    async def test_an_abort_of_the_handler_passes(self) -> None:
        project, stub = await self.start()
        error = await self.call(stub, "abort")
        self.assertEqual(error.code(), grpc.StatusCode.NOT_FOUND)
        decoded = await self.decode(project, error)
        self.assertEqual((decoded.code, decoded.message), (error.code(), "gone"))
        self.assertEqual((decoded.domain, decoded.reason), ("", ""))
        call = stub.ServerStream(EchoRequest(text="abort"))
        self.assertEqual((await read(call)).text, "first")
        with self.assertRaises(aio.AioRpcError) as raised:
            await call.read()
        self.assertEqual(raised.exception.code(), grpc.StatusCode.NOT_FOUND)

    async def test_every_kind_of_rpc_encodes_its_exceptions(self) -> None:
        project, stub = await self.start()
        with self.assertRaises(aio.AioRpcError) as raised:
            await stub.ClientStream(requests("funds"))
        decoded = await self.decode(project, raised.exception)
        self.assertEqual(decoded.reason, "INSUFFICIENT_FUNDS")
        call = stub.ServerStream(EchoRequest(text="funds"))
        self.assertEqual((await read(call)).text, "first")
        with self.assertRaises(aio.AioRpcError) as raised:
            await call.read()
        decoded = await self.decode(project, raised.exception)
        self.assertEqual(decoded.reason, "INSUFFICIENT_FUNDS")
        bidi = stub.BidiStream(requests("funds"))
        self.assertEqual((await read(bidi)).text, "first")
        with self.assertRaises(aio.AioRpcError) as raised:
            await bidi.read()
        decoded = await self.decode(project, raised.exception)
        self.assertEqual(decoded.reason, "INSUFFICIENT_FUNDS")


class GrpcErrorTestCase(unittest.TestCase):
    def make(self, *details: Message) -> GrpcError:
        status = status_pb2.Status(code=grpc.StatusCode.ABORTED.value[0], message="m")
        for detail in details:
            packed = any_pb2.Any()
            packed.Pack(detail)
            status.details.append(packed)
        return GrpcError.from_status(status)

    def test_the_error_info_is_read(self) -> None:
        error = self.make(
            error_details_pb2.ErrorInfo(domain="d", reason="R", metadata={"k": "v"})
        )
        self.assertEqual(error.code, grpc.StatusCode.ABORTED)
        self.assertEqual((str(error), error.message), ("m", "m"))
        self.assertEqual(
            (error.domain, error.reason, error.metadata), ("d", "R", {"k": "v"})
        )

    def test_without_details_the_error_info_is_empty(self) -> None:
        error = self.make()
        self.assertEqual((error.domain, error.reason, error.metadata), ("", "", {}))
        self.assertIsNone(error.find_detail(error_details_pb2.RetryInfo))

    def test_an_unknown_code_is_unknown(self) -> None:
        error = GrpcError.from_status(status_pb2.Status(code=99, message="m"))
        self.assertEqual(error.code, grpc.StatusCode.UNKNOWN)

    def test_the_handler_decodes_a_status_into_a_grpc_error(self) -> None:
        error = self.make(error_details_pb2.ErrorInfo(domain="other", reason="X"))
        with mock.patch.dict(os.environ, clear=True):
            project = TstProject()
            decoded = project.grpc.errors.client_handler.decode(error.status)
        self.assertEqual(decoded.status, error.status)

    def test_the_error_pickles(self) -> None:
        error = self.make(error_details_pb2.ErrorInfo(domain="d", reason="R"))
        copy = pickle.loads(pickle.dumps(error))
        self.assertEqual((copy.message, copy.reason), ("m", "R"))


class RecordingInterceptor(aio.ServerInterceptor):
    def __init__(self) -> None:
        self.methods: list[str] = []

    @t.override
    async def intercept_service[Request, Response](
        self,
        continuation: t.Callable[
            [grpc.HandlerCallDetails],
            t.Awaitable[grpc.RpcMethodHandler[Request, Response] | None],
        ],
        handler_call_details: grpc.HandlerCallDetails,
    ) -> grpc.RpcMethodHandler[Request, Response] | None:
        self.methods.append(handler_call_details.method)
        return await continuation(handler_call_details)


RECORDING = RecordingInterceptor()


class RecordingGrpcServer(FailingGrpcServer):
    @t.override
    def _iter_interceptors(self) -> Iterator[aio.ServerInterceptor]:
        yield from super()._iter_interceptors()
        yield RECORDING


class RecordingGrpcServers(TstGrpcServers):
    default = Slot(RecordingGrpcServer)


class RecordingGrpcUnit(TstGrpcUnit):
    servers = Slot(RecordingGrpcServers)


class RecordingProject(TstProject):
    grpc = Slot(RecordingGrpcUnit)


class InterceptorTestCase(ServerFixture):
    async def test_a_server_adds_interceptors_of_its_own(self) -> None:
        project = RecordingProject()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        server = await project.grpc.servers.default
        [address] = server.addresses
        channel = aio.insecure_channel(address)
        self.addAsyncCleanup(channel.close)
        with self.assertRaises(aio.AioRpcError) as raised:
            await tst_pb2_grpc.EchoStub(channel).Unary(EchoRequest(text="funds"))
        self.assertEqual(RECORDING.methods, ["/tst.Echo/Unary"])
        decoded = project.grpc.errors.client_handler.decode_rpc_error(raised.exception)
        self.assertEqual(decoded.reason, "INSUFFICIENT_FUNDS")


class StockPolicy(BaseGrpcErrorPolicy):
    """A strategy of its own: the reason depends on the exception."""

    EXCEPTION = OutOfStock

    @t.override
    def _encode(self, error: Exception) -> status_pb2.Status:
        reason = "EMPTY" if str(error) == "empty" else "LOW"
        status = status_pb2.Status(code=grpc.StatusCode.ABORTED.value[0])
        status.details.add().Pack(
            error_details_pb2.ErrorInfo(domain="stock.example.com", reason=reason)
        )
        return status


class StockGrpcErrors(GrpcErrors):
    stock = Slot(StockPolicy)


class StockGrpcUnit(GrpcUnit):
    errors = Slot(StockGrpcErrors)


class StockProject(GrpcProject):
    grpc = Slot(StockGrpcUnit)


class StrategyTestCase(unittest.TestCase):
    def test_a_policy_of_its_own_chooses_the_status(self) -> None:
        with mock.patch.dict(os.environ, clear=True):
            project = StockProject()
        handler = project.grpc.errors.server_handler
        for text in ("empty", "low"):
            with self.subTest(text), self.assertLogs("ingot_grpcio", "INFO") as logs:
                status = handler.handle(OutOfStock.build(text), "/tst.Echo/Unary")
            self.assertIn(f"stock.example.com/{text.upper()}", logs.output[0])
            self.assertEqual(GrpcError.from_status(status).reason, text.upper())


class RegistryTestCase(unittest.TestCase):
    def test_the_internal_policy_takes_every_other_exception(self) -> None:
        with mock.patch.dict(os.environ, clear=True):
            project = GrpcProject()
            policy = project.grpc.errors.server_handler.find_policy(KeyError("k"))
        self.assertIsInstance(policy, InternalGrpcErrorPolicy)
        self.assertEqual(
            repr(policy), "<InternalGrpcErrorPolicy ingot_grpcio/INTERNAL>"
        )

    def test_a_policy_logs_at_its_level(self) -> None:
        cases = [
            (logging.INFO, False),
            (logging.WARNING, True),
            (logging.ERROR, False),
            (logging.ERROR, True),
        ]
        for level, is_exc_info in cases:
            with self.subTest(level=level, is_exc_info=is_exc_info):

                class LevelPolicy(ShopErrorPolicy):
                    LOG_LEVEL = level
                    LOG_EXC_INFO = is_exc_info

                class LevelGrpcErrors(GrpcErrors):
                    shop = Slot(LevelPolicy)

                class LevelGrpcUnit(GrpcUnit):
                    errors = Slot(LevelGrpcErrors)

                class LevelProject(GrpcProject):
                    grpc = Slot(LevelGrpcUnit)

                with mock.patch.dict(os.environ, clear=True):
                    project = LevelProject()
                try:
                    raise OutOfStock.build("out of stock")
                except OutOfStock as error:
                    raised = error
                with self.assertLogs("ingot_grpcio", "INFO") as logs:
                    status = project.grpc.errors.server_handler.handle(
                        raised, "/tst.Echo/Unary"
                    )
                [record] = logs.records
                self.assertEqual(record.levelno, level)
                self.assertEqual(
                    record.getMessage(),
                    "/tst.Echo/Unary: OutOfStock('out of stock'), "
                    "shop.example.com/SHOP",
                )
                self.assertEqual(record.exc_info is not None, is_exc_info)
                self.assertEqual(status.message, "out of stock")

    def test_a_policy_declares_its_status(self) -> None:
        with self.assertRaisesRegex(
            TypeError, r"Bad declares no CODE, DOMAIN, REASON$"
        ):

            class Bad(BaseStaticGrpcErrorPolicy):
                EXCEPTION = ShopError

    def test_the_exception_is_an_exception_class(self) -> None:
        with self.assertRaisesRegex(TypeError, r"Bad.EXCEPTION: 'x' is no exception"):

            class Bad(BaseStaticGrpcErrorPolicy):
                EXCEPTION = "x"  # type: ignore[assignment]

    def test_a_policy_without_an_exception_is_a_base(self) -> None:
        class AppPolicy(BaseStaticGrpcErrorPolicy):
            DOMAIN = "app"

        with mock.patch.dict(os.environ, clear=True):
            project = GrpcProject()
            self.assertRegex(repr(AppPolicy(project)), r"^<\S*AppPolicy app/->$")

    def test_a_policy_in_the_registry_declares_its_exception(self) -> None:
        class AppPolicy(BaseStaticGrpcErrorPolicy):
            pass

        with self.assertRaisesRegex(
            TypeError, r"Bad.app: .*AppPolicy declares no EXCEPTION$"
        ):

            class Bad(GrpcErrors):
                app = Slot(AppPolicy)

    def test_an_exception_has_one_policy(self) -> None:
        class OtherShopErrorPolicy(ShopErrorPolicy):
            REASON = "OTHER"

        with self.assertRaisesRegex(
            TypeError, r"Bad: ShopError has both shop and other$"
        ):

            class Bad(GrpcErrors):
                shop = Slot(ShopErrorPolicy)
                other = Slot(OtherShopErrorPolicy)

    def test_a_domain_and_reason_have_one_policy(self) -> None:
        class OutOfStockPolicy(ShopErrorPolicy):
            EXCEPTION = OutOfStock

        with self.assertRaisesRegex(
            TypeError, r"Bad: shop.example.com/SHOP has both shop and stock$"
        ):

            class Bad(GrpcErrors):
                shop = Slot(ShopErrorPolicy)
                stock = Slot(OutOfStockPolicy)
