from typing import Protocol

from src.discriminators.binding.graph import Graph
from src.discriminators.binding.repositories.repository import Repository


class BindingStrategy(Protocol):
    def __init__(self, repository: Repository) -> None: ...

    def graph(self) -> Graph: ...
