"""
The project of the echo, of the units of its parts: the domain, ``echo``,
of no transport, an RPC answering by an operation run for the anonymous
caller, another failing by an error its policy encodes, so that the load
measures what ingot-grpcio adds to grpcio, on a call and on a failure;
``extensions``, what it extends of the framework and of the addon, the
settings, the logging, the operations and gRPC.
"""

__all__ = ("EchoProject",)

from ingot_grpcio import GrpcProject
from ingots.puer import Slot

from echo import EchoUnit
from extensions.grpcio import EchoGrpcUnit
from extensions.logging import EchoLoggingUnit
from extensions.operations import EchoOperationsUnit
from extensions.settings import EchoSettingsUnit


class EchoProject(GrpcProject):
    env_configs_prefix = "APP"
    settings = Slot(EchoSettingsUnit)
    logging = Slot(EchoLoggingUnit)
    operations = Slot(EchoOperationsUnit)
    grpc = Slot(EchoGrpcUnit)
    echo = Slot(EchoUnit)
