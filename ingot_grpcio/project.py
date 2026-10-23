"""The project of the addon: what an application inherits from."""

__all__ = ("Project",)

from ingots.defaults import Project as BaseProject
from ingots.puer import Slot

from .logging import Logging
from .settings import Settings


class Project(BaseProject):
    """
    The project of the defaults with the addon's :class:`Settings` and
    :class:`Logging`. An application inherits from it and sets its own
    ``env_configs_prefix``; the addon run on its own (``python -m ingot_grpcio``)
    keeps the prefix of the defaults, ``INGOT``.
    """

    settings = Slot(Settings)
    logging = Slot(Logging)
