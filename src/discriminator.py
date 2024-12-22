import os
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

import rich.progress

from src.binding.repository import JavaRepository
from src.binding.file_types import FileName, SourceFile, TestFile
from src.binding.import_strategy import ImportStrategy
from src.binding.strategy import BindingStrategy
from src.transaction import TransactionLog, TransactionMap, Transactions

console = rich.console.Console()


class Statistics(Protocol):
    def output(self) -> str: ...


class Discriminator(Protocol):
    transaction: TransactionLog
    file_binder: BindingStrategy

    def __init__(self, transactions: Transactions, file_binder: BindingStrategy): ...

    @property
    def statistics(self) -> Statistics: ...


@dataclass(frozen=True)
class TestStatistics:
    test: TestFile
    before: list[SourceFile]
    after: list[SourceFile]


@dataclass(frozen=True)
class BeforeAfterStatistics(Statistics):
    test_statistics: list[TestStatistics]

    @cached_property
    def aggregate_before(self) -> set[SourceFile]:
        return set().union(*[statistic.before for statistic in self.test_statistics])

    @cached_property
    def aggregate_after(self) -> set[SourceFile]:
        return set().union(*[statistic.after for statistic in self.test_statistics])

    @cached_property
    def test_first(self) -> set[SourceFile]:
        return self.aggregate_before - self.aggregate_after

    def output(self) -> str:
        return (
            f"Test First: {len(self.test_first)}\n"
            + f"Test After: {len(self.aggregate_after)}"
        )


@dataclass(frozen=True)
class BeforeAfterDiscriminator(Discriminator):
    transaction: TransactionLog
    file_binder: BindingStrategy

    @property
    def statistics(self) -> BeforeAfterStatistics:
        output = []
        graph = self.file_binder.graph()
        for test in rich.progress.track(graph.test_files):
            path = FileName(os.path.join(os.path.basename(test.project), test.path))
            file_number = self.transaction.mapping.name_to_id[path]
            base_commit = self.transaction.transactions.first_occurrence(file_number)
            assert base_commit is not None, f"File not found {test.name} @ {path}"
            before, after = [], []

            for source_file in graph.links[test]:
                path = FileName(
                    os.path.join(
                        os.path.basename(source_file.project), source_file.path
                    )
                )
                file_number = self.transaction.mapping.name_to_id[path]
                assert (
                    file_number is not None
                ), f"File not found {source_file.name} @ {path}"
                commit = self.transaction.transactions.first_occurrence(file_number)
                assert commit
                if commit.number < base_commit.number:
                    before.append(source_file)
                else:
                    after.append(source_file)
            if before or after:
                output.append(TestStatistics(test, before, after))
        return BeforeAfterStatistics(test_statistics=output)


if __name__ == "__main__":
    with open("transactions.txt") as t, open("mapping.json") as m:
        logs = Transactions.deserialize(t.read())
        mapping = TransactionMap.deserialize(m.read())

    transactions = TransactionLog(logs, mapping)
    discriminator = BeforeAfterDiscriminator(
        transactions, ImportStrategy(JavaRepository(os.path.abspath("../zookeeper")))
    )

    print(discriminator.statistics.output())
