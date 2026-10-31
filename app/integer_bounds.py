"""Limits for externally supplied SQL INTEGER keys and counters."""
from typing import Annotated

from pydantic import Field
from starlette.convertors import Convertor, register_url_convertor


SQL_INTEGER_MAX = 2**31 - 1
PositiveDatabaseId = Annotated[int, Field(gt=0, le=SQL_INTEGER_MAX)]


class _DatabaseIdConvertor(Convertor[int]):
    # Profile aliases retain their numeric-only routing without passing an
    # arbitrarily long decimal string to Python's int() before validation.
    regex = r"[0-9]{1,10}"

    def convert(self, value: str) -> int:
        return int(value)

    def to_string(self, value: int) -> str:
        return str(value)


register_url_convertor("database_id", _DatabaseIdConvertor())
