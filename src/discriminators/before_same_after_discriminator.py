from dataclasses import dataclass
from functools import cached_property

import rich.progress

from src.discriminators.binding.file_types import FileName, SourceFile, TestFile
from src.discriminators.binding.graph import Graph
from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.discriminator import Discriminator, Statistics
from src.discriminators.file_types import FileChanges
from src.discriminators.transaction import TransactionBuilder, TransactionLog

console = rich.console.Console()


@dataclass(frozen=True)
class TestStatistics:
    test: TestFile
    before: list[SourceFile]
    after: list[SourceFile]
    same: list[SourceFile]


@dataclass(frozen=True)
class BeforeSameAfterStatistics(Statistics):
    test_statistics: list[TestStatistics]
    graph: Graph

    @cached_property
    def aggregate_before(self) -> set[SourceFile]:
        return set().union(*[statistic.before for statistic in self.test_statistics])

    @cached_property
    def aggregate_same(self) -> set[SourceFile]:
        return set().union(*[statistic.same for statistic in self.test_statistics])

    @cached_property
    def aggregate_after(self) -> set[SourceFile]:
        return set().union(*[statistic.after for statistic in self.test_statistics])

    @cached_property
    def test_same(self) -> set[SourceFile]:
        return self.aggregate_same - self.aggregate_before

    @cached_property
    def test_after(self) -> set[SourceFile]:
        return (self.aggregate_after - self.aggregate_before) - self.aggregate_same

    @property
    def untested_source_files(self) -> set[SourceFile]:
        return (
            (self.graph.source_files - self.aggregate_before) - self.aggregate_after
        ) - self.aggregate_same

    def output(self) -> str:
        return (
            f"Test First: {len(self.aggregate_before)}\n"
            f"Test Same: {len(self.test_same)}\n"
            + f"Test After: {len(self.test_after)}\n"
            + f"Untested Files: {len(self.untested_source_files)}\n"
        )


@dataclass(frozen=True)
class BeforeSameAfterDiscriminator(Discriminator):
    commit_data: list[FileChanges]
    file_binder: BindingStrategy

    @cached_property
    def transaction(self) -> TransactionLog:
        return TransactionBuilder.build_from_groups(
            TransactionBuilder.group_file_changes(self.commit_data)
        )

    @property
    def statistics(self) -> BeforeSameAfterStatistics:
        output = []
        graph = self.file_binder.graph()
        print(f"Graph has {len(graph.test_files)} test files")
        print(f"Graph has {len(graph.source_files)} source files")
        print(f"Graph has {len(graph.test_to_source_links)} links")
        for test in rich.progress.track(graph.test_files):
            path = FileName(test.path)
            file_number = self.transaction.mapping.name_to_id[path]
            base_commit = self.transaction.transactions.first_occurrence(file_number)
            assert base_commit is not None, f"Test file not found {test.name} @ {path}"
            before, after, same = [], [], []
            for source_file in graph.test_to_source_links[test]:
                path = FileName(source_file.path)
                file_number = self.transaction.mapping.name_to_id[path]
                assert (
                    file_number is not None
                ), f"Source file not found {source_file.name} @ {path}"
                commit = self.transaction.transactions.first_occurrence(file_number)
                assert commit
                if commit.number < base_commit.number:
                    before.append(source_file)
                elif commit.number == base_commit.number:
                    same.append(source_file)
                else:
                    after.append(source_file)
            if before or same or after:
                output.append(
                    TestStatistics(test, before=before, after=after, same=same)
                )
        return BeforeSameAfterStatistics(test_statistics=output, graph=graph)
