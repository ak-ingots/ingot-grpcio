"""
What the scenarios of the load of the echo share: the project of the
client with the configs of a run, ``PerfConfigs`` of ingots joined to its
own, and the client of the floor of the stand, grpcio alone, on
``ECHO_BARE_PORT``.
"""

import typing as t

from ingot_grpcio.grpc import GrpcCliUnit
from ingot_grpcio.settings import GrpcSettingsUnit
from ingot_grpcio.settings.configs import GrpcConfigs
from ingots.defaults.settings.configs import IntConfig
from ingots.perf import PerfCliUnit, PerfConfigs, PerfStandProject
from ingots.puer import Slot

from client.project import EchoClientGrpcUnit, EchoClientProject, EchoGrpcClient
from client.project import EchoGrpcClientsUnit


class EchoPerfConfigs(GrpcConfigs, PerfConfigs):
    # the port of the floor, grpcio alone; the application on GRPC_DEFAULT_*
    ECHO_BARE_PORT = IntConfig(50072)


class EchoPerfSettingsUnit(GrpcSettingsUnit):
    configs = Slot(EchoPerfConfigs)


class BareEchoGrpcClient(EchoGrpcClient):
    """The client of the floor, on ``ECHO_BARE_PORT``."""

    project: "EchoPerfProject"

    @t.override
    def _get_target(self) -> str:
        configs = self.project.settings.configs
        return f"{configs.GRPC_DEFAULT_HOST}:{configs.ECHO_BARE_PORT}"


class EchoPerfGrpcClientsUnit(EchoGrpcClientsUnit):
    bare = Slot(BareEchoGrpcClient)


class EchoPerfGrpcUnit(EchoClientGrpcUnit):
    clients = Slot(EchoPerfGrpcClientsUnit)


class EchoPerfCliUnit(PerfCliUnit, GrpcCliUnit):
    pass


class EchoPerfProject(PerfStandProject, EchoClientProject):
    """The project of a scenario, which adds its unit ``perf``."""

    env_configs_prefix = "PERF_TEST"
    settings = Slot(EchoPerfSettingsUnit)
    grpc = Slot(EchoPerfGrpcUnit)
    cli = Slot(EchoPerfCliUnit)


# the text of every echo: its size is not under test
TEXT: t.Final = "hello"
