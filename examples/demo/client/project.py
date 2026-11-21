"""The project of a client of the echo: the client of ingot-grpcio of the app."""

from echo.v1 import echo_pb2_grpc
from ingot_grpcio import GrpcProject
from ingot_grpcio.grpc import GrpcUnit
from ingot_grpcio.grpc.clients import DefaultGrpcClient, GrpcClientsUnit
from ingot_grpcio.grpc.services import GrpcService
from ingots.puer import Slot


class EchoGrpcClient(DefaultGrpcClient):
    """The client of the echo of the application."""

    echo = GrpcService(echo_pb2_grpc.EchoServiceStub)


class EchoGrpcClientsUnit(GrpcClientsUnit):
    default = Slot(EchoGrpcClient)


class EchoClientGrpcUnit(GrpcUnit):
    clients = Slot(EchoGrpcClientsUnit)


class EchoClientProject(GrpcProject):
    env_configs_prefix = "ECHO_TEST"
    grpc = Slot(EchoClientGrpcUnit)
