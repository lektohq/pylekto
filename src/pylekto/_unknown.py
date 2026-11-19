"""A value of a choice that a newer Lekto sends and this pylekto does not know yet."""

from typing import TYPE_CHECKING

from pydantic_core import CoreSchema, core_schema

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler


class Unknown(str):
    """A value of a choice that this pylekto does not know, as Lekto sent it.

    Every choice in :mod:`pylekto.models` (``Literal[...]``) also takes an ``Unknown``: a newer
    Lekto may send a value that did not exist when this pylekto was made, and reading it does not
    fail. A plain ``str`` is no ``Unknown``, so a type checker still holds requests to the known
    values.

    Example::

        health = await lekto.health.get()
        match health.status:
            case "ok" | "degraded" | "unavailable":
                show(health.status)
            case Unknown():
                print("a state this pylekto does not know:", health.status)

    """

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source: object, _handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Take any text, but only in lax mode, where pydantic tries it after the known values."""
        return core_schema.lax_or_strict_schema(
            lax_schema=core_schema.no_info_after_validator_function(cls, core_schema.str_schema()),
            strict_schema=core_schema.is_instance_schema(cls),
        )
