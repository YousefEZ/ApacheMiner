import os
from dataclasses import dataclass
from functools import cached_property
from typing import Protocol

import rich.progress

from src.binder import Repository, SubProject
from src.binding.file_types import FileName, SourceFile, TestFile
from src.transaction import TransactionLog, TransactionMap, Transactions

console = rich.console.Console()


class Statistics(Protocol):
    def output(self) -> str: ...


class Discriminator(Protocol):
    transaction: TransactionLog
    subproject: SubProject

    def __init__(self, transactions: Transactions, subproject: SubProject): ...

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
        return f"Test First: {len(self.test_first)}\nTest After: {len(self.aggregate_after)}"


@dataclass(frozen=True)
class BeforeAfterDiscriminator(Discriminator):
    transaction: TransactionLog
    subproject: SubProject

    @property
    def statistics(self) -> BeforeAfterStatistics:
        output = []
        graph = self.subproject.graph
        for test in rich.progress.track(self.subproject.tests):
            path = FileName(
                os.path.join(os.path.basename(self.subproject.path), test.path)
            )
            file_number = self.transaction.mapping.name_to_id[path]
            base_commit = self.transaction.transactions.first_occurrence(file_number)
            assert base_commit is not None, f"File not found {test.name} @ {path}"
            before, after = [], []

            for source_file in graph.links[test]:
                path = FileName(
                    os.path.join(
                        os.path.basename(self.subproject.path), source_file.path
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
    repo = Repository(os.path.abspath("../zookeeper"))
    for subproject in repo.subprojects:
        with open("transactions.txt") as t, open("mapping.json") as m:
            logs = Transactions.deserialize(t.read())
            mapping = TransactionMap.deserialize(m.read())

        transactions = TransactionLog(logs, mapping)
        subproject_discriminator = BeforeAfterDiscriminator(transactions, subproject)

        print(f"Analyzing subproject: {subproject.path}")
        print(subproject_discriminator.statistics.output())
