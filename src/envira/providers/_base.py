from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Optional, TypeVar, get_args

from pydantic import BaseModel


class BasePattern(BaseModel):
    pass


_T_Pattern = TypeVar("_T_Pattern", bound=BasePattern)


class BaseProvider(ABC, Generic[_T_Pattern]):
    pattern: _T_Pattern
    section_key: str

    def __init__(self, section: Dict) -> None:
        self.pattern = get_args(self.__orig_bases__[0])[0]  # type: ignore
        self.section = section

        self.validate()

    def validate(self) -> None:
        self.section_obj = self.pattern.parse_obj(self.section)

    @abstractmethod
    def apply(self, *args, **kwargs) -> None:
        raise NotImplementedError

    @property
    @abstractmethod
    def priority(self) -> int:
        raise NotImplementedError


class ProviderOperationResult(BaseModel):
    cmd: Optional[str]
    exit_code: Optional[int]
    operation_log: Optional[str]
    err: Optional[str]
    data: Optional[Any]


def provider_cmd_error(res: ProviderOperationResult) -> None:
    print(
        (f"Command '{res.cmd}' " if res.cmd else "Operation ")
        + "exit with error"
        + (f" code {res.exit_code}, " if res.exit_code else ", ")
        + f"reason: {res.err}"
    )
