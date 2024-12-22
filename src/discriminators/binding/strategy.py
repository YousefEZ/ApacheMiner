from typing import Protocol

from .graph import Graph
from .repository import Repository


class BindingStrategy(Protocol):
    def __init__(self, repository: Repository) -> None: ...

    def graph(self) -> Graph: ...
