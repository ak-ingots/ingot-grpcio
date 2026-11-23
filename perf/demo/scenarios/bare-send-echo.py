"""The floor of an echo: the same call to the service on grpcio alone."""

import typing as t

from load import TEXT, EchoPerfProject
from echo.v1.echo_pb2 import SendEchoRequest
from ingots.perf import LoadClient, LoadGroup, PerfUnit
from ingots.puer import Slot


class BareSender(LoadClient["PerfProject", "BareSenderGroup"]):
    @t.override
    async def asyncSetUp(self) -> None:
        self.echo = (await self.project.grpc.clients.bare).echo

    @t.override
    async def run(self) -> None:
        async with self.measure("send-echo"):
            await self.echo.SendEcho(SendEchoRequest(text=TEXT))


class BareSenderGroup(LoadGroup[None]):
    clients = (BareSender,)


class BareSendEchoPerf(PerfUnit[None]):
    group = BareSenderGroup


class PerfProject(EchoPerfProject):
    perf = Slot(BareSendEchoPerf)
