"""The servicer: the implementation of the RPCs of a service."""

__all__ = ("GrpcServicer",)

import typing as t

from ingots.puer import Entity

if t.TYPE_CHECKING:
    from grpc import aio
    from ingots.defaults import Project
    from ingots.defaults.operations import BaseOperation, Caller
    from ingots.puer import BoundFactory


class GrpcServicer(Entity):
    """
    A servicer: the implementation of the RPCs of a service, extending the
    generated base class too. It reaches the project as any entity does::

        class Echo(GrpcServicer, demo_pb2_grpc.EchoServicer):
            @t.override
            async def Say(self, request, context): ...

    A :class:`~ingot_grpcio.grpc.services.GrpcService` names it; a server
    serving the service creates it, one for the server.

    An RPC runs an operation of the project by :meth:`run_operation`, for
    the caller of the call that :meth:`_get_caller` tells, the anonymous one
    of the project here, with what the application gives anyone: how a call
    tells its caller, a token, a certificate, is of the application or of an
    addon, which overrides the hook.
    """

    project: "Project"

    @t.final
    async def run_operation[ParametersType, ResultType](
        self,
        factory: "BoundFactory[BaseOperation[ParametersType, ResultType]]",
        parameters: ParametersType,
        context: "aio.ServicerContext[t.Any, t.Any]",
    ) -> ResultType:
        """Runs an operation for the caller of a call."""
        operations = self.project.operations
        metadata = operations.create_metadata(await self._get_caller(context))
        return await operations.runner.run(factory, parameters, metadata)

    async def _get_caller(
        self, context: "aio.ServicerContext[t.Any, t.Any]"
    ) -> "Caller":
        """
        The caller of a call, of what it bears: the anonymous one here, of
        ``operations.callers``, with what the application gives anyone.
        """
        return self.project.operations.callers.get_anonymous()
