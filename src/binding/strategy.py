from typing import Protocol

from src.binding.graph import Graph


class BindingStrategy(Protocol):
    def __init__(self, path: str) -> None: ...

    def graph(self) -> Graph: ...
