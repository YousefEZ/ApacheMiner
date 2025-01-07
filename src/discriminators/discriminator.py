from typing import Protocol

import rich.progress
from git import PathLike

from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.file_types import FileChanges
from src.discriminators.transaction import TransactionLog

console = rich.console.Console()


class Statistics(Protocol):
    def output(self) -> str: ...


class Discriminator(Protocol):
    transaction: TransactionLog
    file_binder: BindingStrategy
    commit_data: list[FileChanges]

    def __init__(
        self,
        transactions: TransactionLog,
        file_binder: BindingStrategy,
        repository: PathLike,
    ): ...

    @property
    def statistics(self) -> Statistics: ...
