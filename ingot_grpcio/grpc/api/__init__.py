"""The API: the registry of the services of the project."""

__all__ = ("GrpcApi", "GrpcService", "GrpcServicer")

import typing as t

from ingots.puer import Unit

from .services import GrpcService, GrpcServicer


class GrpcApi(Unit):
    """
    The services of the project, each in a slot of its own. Empty here: an
    application adds its services in a subclass, and the bindings choose
    which of them each server serves::

        class AppGrpcApi(GrpcApi):
            echo = Slot(EchoService)

    A service is in the API once: two slots of one service fail the class.
    """

    @t.override
    @classmethod
    def __init_subclass__(cls, **kwargs: t.Any) -> None:
        super().__init_subclass__(**kwargs)
        check_services(cls)


def check_services(cls: type[GrpcApi]) -> None:
    """
    Internal, run when the class is created: every service of the API is a
    service of a ``.proto`` file, and none is in it twice.
    """
    owners: dict[str, str] = {}
    for name, slot in cls.slots_iter(GrpcService):
        full_name = getattr(slot.cls, "FULL_NAME", None)
        if full_name is None:
            raise TypeError(
                f"{cls.__qualname__}.{name}: {slot.cls.__qualname__} declares no "
                f"FULL_NAME"
            )
        owner = owners.setdefault(full_name, name)
        if owner != name:
            raise TypeError(
                f"{cls.__qualname__}: {full_name!r} is in both {owner} and {name}"
            )
