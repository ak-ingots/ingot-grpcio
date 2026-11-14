import os
import typing as t
import unittest
from unittest import mock

from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.clients import DefaultGrpcClient, GrpcClientsUnit
from ingot_grpcio.grpc.servers import DefaultGrpcServer, GrpcServersUnit
from ingot_grpcio.grpc.services import GrpcService
from ingots.defaults.operations import (
    BaseOperation,
    Caller,
    CallersProvider,
    OperationMetadata,
    OperationsUnit,
    OperationsOwner,
    PermissionFlags,
    Permissions,
    PermissionsSlot,
)
from ingots.puer import Factory, Slot, Unit, create_entity

from .proto import tst_pb2_grpc
from .proto.tst_pb2 import EchoReply, EchoRequest
from .test_client import Context, Echo, find_free_port


class GreetOperation(BaseOperation[str, str]):
    """Greets the caller it runs for, who may greet."""

    parent: "TstUnit"

    @t.override
    def _get_permissions(self) -> Permissions:
        permissions = self.parent.permissions
        return permissions(permissions.flags.CAN_GREET)

    @t.override
    async def _run(self, parameters: str, metadata: OperationMetadata) -> str:
        return f"{parameters}, {metadata.caller.uid}"


class TstUnit(OperationsOwner, Unit):
    class Flags(PermissionFlags):
        CAN_GREET = 1 << 0

    permissions = PermissionsSlot(Flags)

    op_greet = Factory(GreetOperation)


# who may greet, of the domain of the unit, tst
GREETER: t.Final = Permissions({"tst": TstUnit.Flags.CAN_GREET})


class TstCallers(CallersProvider):
    """Anyone may greet."""

    @t.override
    def _get_anonymous_permissions(self) -> Permissions:
        return super()._get_anonymous_permissions() | GREETER


class TstOperationsUnit(OperationsUnit):
    callers = Slot(TstCallers)


class AnonymousEcho(Echo):
    """Greets by the operation, for the caller of the base."""

    project: "TstProject"

    @t.override
    async def Unary(self, request: EchoRequest, context: Context) -> EchoReply:
        greet = self.project.tst.op_greet
        return EchoReply(text=await self.run_operation(greet, request.text, context))


class GreetingEcho(AnonymousEcho):
    """The caller of a call is the one its metadata ``caller`` names."""

    @t.override
    async def _get_caller(self, context: Context) -> Caller:
        metadata = dict(context.invocation_metadata() or ())
        greeter = GREETER
        return Caller(uid=str(metadata["caller"]), permissions=greeter)


class TstGrpcBinding:
    echo = GrpcService(tst_pb2_grpc.EchoStub, GreetingEcho)


class TstGrpcServer(TstGrpcBinding, DefaultGrpcServer):
    pass


class TstGrpcClient(TstGrpcBinding, DefaultGrpcClient):
    pass


class TstGrpcServersUnit(GrpcServersUnit):
    default = Slot(TstGrpcServer)


class TstGrpcClientsUnit(GrpcClientsUnit):
    default = Slot(TstGrpcClient)


class TstGrpcUnit(GrpcUnit):
    servers = Slot(TstGrpcServersUnit)
    clients = Slot(TstGrpcClientsUnit)


class TstProject(GrpcProject):
    operations = Slot(TstOperationsUnit)
    grpc = Slot(TstGrpcUnit)
    tst = Slot(TstUnit)


class OperationsTestCase(unittest.IsolatedAsyncioTestCase):
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

    async def test_an_operation_runs_for_the_caller_of_the_call(self) -> None:
        project = TstProject()
        await project._configure()
        self.addAsyncCleanup(project._do_shut_down)
        await project.grpc.servers.default
        with self.assertLogs("ingot_grpcio", "INFO"):
            client = await project.grpc.clients.default
        reply = await client.echo.Unary(
            EchoRequest(text="hi"), metadata=(("caller", "alice"),)
        )
        self.assertEqual(reply.text, "hi, alice")

    async def test_the_caller_is_the_anonymous_one_of_the_project(self) -> None:
        # with what the project gives anyone: greeting
        project = TstProject()
        servicer = create_entity(AnonymousEcho, project)
        reply = await servicer.Unary(EchoRequest(text="hi"), mock.Mock())
        self.assertEqual(reply.text, "hi, anonymous")
