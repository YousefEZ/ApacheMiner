from typing import Protocol

import rich.progress

from src.discriminators.binding.strategy import BindingStrategy
from src.transaction import TransactionLog, Transactions

console = rich.console.Console()


class Statistics(Protocol):
    def output(self) -> str: ...


class Discriminator(Protocol):
    transaction: TransactionLog
    file_binder: BindingStrategy

    def __init__(self, transactions: Transactions, file_binder: BindingStrategy): ...

    @property
    def statistics(self) -> Statistics: ...
