from typing import Protocol

import rich.progress

from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.file_types import FileChanges

console = rich.console.Console()


class Statistics(Protocol):
    def output(self) -> str: ...


class Discriminator(Protocol):
    commit_data: list[FileChanges]
    file_binder: BindingStrategy

    def __init__(
        self,
        commit_data: list[FileChanges],
        file_binder: BindingStrategy,
    ): ...

    @property
    def statistics(self) -> Statistics: ...
