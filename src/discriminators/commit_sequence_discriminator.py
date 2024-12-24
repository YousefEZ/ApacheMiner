import os
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property

import rich.progress

from .binding.file_types import FileName, ProgramFile, SourceFile
from .binding.graph import Graph
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .transaction import Commit, FileNumber, TransactionLog, modification_map

console = rich.console.Console()
LENIENCY = 0


@dataclass(frozen=True)
class Stats:
    source: SourceFile
    changed_tests_per_commit: list[dict[ProgramFile, list[Commit]]]

    @cached_property
    def is_tfd(self) -> bool:
        leniency_counter = 0
        for changed_tests in self.changed_tests_per_commit:
            if len(changed_tests) == 0:
                leniency_counter += 1
            if leniency_counter > LENIENCY:
                return False
        return True


@dataclass(frozen=True)
class TestedFirstStatistics(Statistics):
    test_statistics: list[Stats]

    @cached_property
    def test_first(self) -> set[SourceFile]:
        return set(
            [statistic.source for statistic in self.test_statistics if statistic.is_tfd]
        )

    @cached_property
    def non_test_first(self) -> set[SourceFile]:
        return (
            set([statistic.source for statistic in self.test_statistics])
            - self.test_first
        )

    def output(self) -> str:
        return (
            f"Test First Updates: {len(self.test_first)}\n"
            + f"Test Elsewhere: {len(self.non_test_first)}"
        )


@dataclass(frozen=True)
class CommitSequenceDiscriminator(Discriminator):
    transaction: TransactionLog
    file_binder: BindingStrategy

    @property
    def graph(self) -> Graph:
        return self.file_binder.graph()

    def tfd_iterations(
        self,
        source_id: FileNumber,
        i: int,
        tests: set[ProgramFile],
    ) -> tuple[dict[ProgramFile, list[Commit]], Commit]:
        hits: dict[ProgramFile, list[Commit]] = defaultdict(list)
        for commit in self.transaction.transactions.commits[i:]:
            for test_file in tests:
                path = FileName(
                    os.path.join(os.path.basename(test_file.project), test_file.path)
                )
                test_id = self.transaction.mapping.name_to_id[path]

                if (
                    test_id in commit.files
                    and modification_map[commit.files[test_id]] == "M"
                ):
                    hits[test_file].append(commit)
                    # TODO: check coverage updates in improved version

            if source_id in commit.files:
                if (
                    modification_map[commit.files[source_id]] == "M"
                    or modification_map[commit.files[source_id]] == "D"
                ):
                    return hits, commit  # return early if source file is updated
        return hits, self.transaction.transactions.commits[-1]

    @property
    def statistics(self) -> TestedFirstStatistics:
        output = []
        graph = self.graph
        for source_file in rich.progress.track(graph.source_files):
            if source_file not in graph.links:
                continue  # no tests for this source file
            path = FileName(
                os.path.join(os.path.basename(source_file.project), source_file.path)
            )
            source_id = self.transaction.mapping.name_to_id[path]
            stats = Stats(source_file, [])
            last_commit = self.transaction.transactions.first_occurrence(source_id)
            if last_commit is None:
                continue  # never appears in the transaction log
            while (
                modification_map[last_commit.files[source_id]] != "D"
                and last_commit.number < len(self.transaction.transactions.commits) - 1
            ):
                hits, last_commit = self.tfd_iterations(
                    source_id, last_commit.number + 1, graph.links[source_file]
                )
                stats.changed_tests_per_commit.append(hits)
                if source_id not in last_commit.files:
                    break  # finished tracking this source file
            output.append(stats)
        return TestedFirstStatistics(test_statistics=output)
