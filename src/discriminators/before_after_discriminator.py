import os
from dataclasses import dataclass
from functools import cached_property

import rich.progress

from src.discriminators.binding.file_types import FileName, SourceFile, TestFile
from src.discriminators.binding.import_strategy import ImportStrategy
from src.discriminators.binding.repository import JavaRepository
from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.discriminator import Discriminator, Statistics
from src.discriminators.transaction import TransactionLog, TransactionMap, Transactions

console = rich.console.Console()


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
