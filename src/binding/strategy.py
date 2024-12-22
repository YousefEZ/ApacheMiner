from typing import Protocol

from src.binding.graph import Graph
from src.binding.repository import Repository


class BindingStrategy(Protocol):
    def __init__(self, repository: Repository) -> None: ...

    def graph(self) -> Graph: ...
