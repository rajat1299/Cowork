from dataclasses import dataclass
from typing import Any


@dataclass
class ToolkitCall:
    name: str
    input: dict[str, Any]


@dataclass
class ToolkitResult:
    name: str
    output: dict[str, Any]


class Toolkit:
    name: str = "base"

    async def run(self, call: ToolkitCall) -> ToolkitResult:
        raise NotImplementedError
