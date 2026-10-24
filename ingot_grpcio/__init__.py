"""
ingot-grpcio: Integration of grpcio, the gRPC library of Google, into Ingots
applications: gRPC servers and clients on its API. An application inherits
from :class:`GrpcProject`, or joins the units of the addon, ``settings`` and
``logging``, with those of its other addons.
"""

__all__ = ("GrpcProject",)

from .project import GrpcProject
