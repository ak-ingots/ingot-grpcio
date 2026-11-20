"""The floor of a failure: a status of grpcio alone, no details."""

import typing as t

import grpc

from project import TEXT, EchoPerfProject
from echo.v1.echo_pb2 import FailEchoRequest
from ingot_grpcio.grpc.errors import GrpcError
from ingots.perf import LoadClient, LoadGroup, PerfUnit
from ingots.puer import Slot


class RawFailer(LoadClient["PerfProject", "RawFailerGroup"]):
    @t.override
    async def asyncSetUp(self) -> None:
        self.echo = (await self.project.grpc.clients.raw).echo

    @t.override
    async def run(self) -> None:
        async with self.measure("fail-echo"):
            try:
                await self.echo.FailEcho(FailEchoRequest(text=TEXT))
            except GrpcError as error:
                if error.code != grpc.StatusCode.FAILED_PRECONDITION:
                    raise


class RawFailerGroup(LoadGroup[None]):
    clients = (RawFailer,)


class RawFailEchoPerf(PerfUnit[None]):
    group = RawFailerGroup


class PerfProject(EchoPerfProject):
    perf = Slot(RawFailEchoPerf)
