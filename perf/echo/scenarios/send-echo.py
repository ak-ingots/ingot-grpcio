"""An echo through the servicer of ingot-grpcio, for the anonymous caller."""

import typing as t

from project import TEXT, EchoPerfProject
from echo.v1.echo_pb2 import SendEchoRequest
from ingots.perf import LoadClient, LoadGroup, PerfUnit
from ingots.puer import Slot


class Sender(LoadClient["PerfProject", "SenderGroup"]):
    @t.override
    async def asyncSetUp(self) -> None:
        self.echo = (await self.project.grpc.clients.default).echo

    @t.override
    async def run(self) -> None:
        async with self.measure("send-echo"):
            await self.echo.SendEcho(SendEchoRequest(text=TEXT))


class SenderGroup(LoadGroup[None]):
    clients = (Sender,)


class SendEchoPerf(PerfUnit[None]):
    group = SenderGroup


class PerfProject(EchoPerfProject):
    perf = Slot(SendEchoPerf)
