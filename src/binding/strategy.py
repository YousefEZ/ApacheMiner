from typing import Protocol

from src.binding.repository import Repository
from src.binding.graph import Graph


class BindingStrategy(Protocol):
    def __init__(self, repository: Repository) -> None: ...

    def graph(self) -> Graph: ...
