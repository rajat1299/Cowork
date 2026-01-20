from app.runtime.toolkits.base import Toolkit

_toolkits: dict[str, Toolkit] = {}


def register(toolkit: Toolkit) -> None:
    _toolkits[toolkit.name] = toolkit


def get_toolkit(name: str) -> Toolkit | None:
    return _toolkits.get(name)


def list_toolkits() -> list[str]:
    return sorted(_toolkits.keys())
