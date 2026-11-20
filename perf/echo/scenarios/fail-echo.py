"""A failure through the policy of ingot-grpcio: the status and its details."""

import typing as t

from project import TEXT, EchoPerfProject
from echo.v1.echo_pb2 import FailEchoRequest
from ingot_grpcio.grpc.errors import GrpcError
from ingots.perf import LoadClient, LoadGroup, PerfUnit
from ingots.puer import Slot


class Failer(LoadClient["PerfProject", "FailerGroup"]):
    @t.override
    async def asyncSetUp(self) -> None:
        self.echo = (await self.project.grpc.clients.default).echo

    @t.override
    async def run(self) -> None:
        async with self.measure("fail-echo"):
            try:
                await self.echo.FailEcho(FailEchoRequest(text=TEXT))
            except GrpcError as error:
                if error.reason != "ECHO_FAILED":
                    raise


class FailerGroup(LoadGroup[None]):
    clients = (Failer,)


class FailEchoPerf(PerfUnit[None]):
    group = FailerGroup


class PerfProject(EchoPerfProject):
    perf = Slot(FailEchoPerf)
