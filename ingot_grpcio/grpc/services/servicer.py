"""The servicer: the implementation of the RPCs of a service."""

__all__ = ("GrpcServicer",)

from ingots.puer import Entity


class GrpcServicer(Entity):
    """
    A servicer: the implementation of the RPCs of a service, extending the
    generated base class too. It reaches the project as any entity does::

        class Echo(GrpcServicer, demo_pb2_grpc.EchoServicer):
            @t.override
            async def Say(self, request, context): ...

    A :class:`~ingot_grpcio.grpc.services.GrpcService` names it; a server
    serving the service creates it, one for the server.
    """
