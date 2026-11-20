"""The floor of an echo: the same call to the service on grpcio alone."""

import typing as t

from project import TEXT, EchoPerfProject
from echo.v1.echo_pb2 import SendEchoRequest
from ingots.perf import LoadClient, LoadGroup, PerfUnit
from ingots.puer import Slot


class RawSender(LoadClient["PerfProject", "RawSenderGroup"]):
    @t.override
    async def asyncSetUp(self) -> None:
        self.echo = (await self.project.grpc.clients.raw).echo

    @t.override
    async def run(self) -> None:
        async with self.measure("send-echo"):
            await self.echo.SendEcho(SendEchoRequest(text=TEXT))


class RawSenderGroup(LoadGroup[None]):
    clients = (RawSender,)


class RawSendEchoPerf(PerfUnit[None]):
    group = RawSenderGroup


class PerfProject(EchoPerfProject):
    perf = Slot(RawSendEchoPerf)
