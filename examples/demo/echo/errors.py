"""The errors of the echo."""

__all__ = ("EchoFailedError",)

import typing as t

from ingots.puer import UserError


class EchoFailedError(UserError):
    """The failure the echo is asked for. Create it with :meth:`for_text`."""

    @classmethod
    def for_text(cls, text: str) -> t.Self:
        return cls(f"the echo of {text!r} failed, as asked", text)

    @property
    def text(self) -> str:
        return t.cast(str, self.args[1])

    @t.override
    def __str__(self) -> str:
        return t.cast(str, self.args[0])
