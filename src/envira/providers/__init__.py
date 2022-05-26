from typing import List, Type

from . import apt, env
from ._base import BaseProvider

__all__ = ["get_providers", "BaseProvider"]


def get_providers() -> List[Type[BaseProvider]]:
    return [apt.AptProvider, env.EnvProvider]
