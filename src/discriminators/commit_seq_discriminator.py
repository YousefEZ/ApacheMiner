import os
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

import rich.progress

from .binding.file_types import FileName, SourceFile, TestFile
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .transaction import Commit, TransactionLog, modification_map

console = rich.console.Console()
LENIENCY = 0


@dataclass(frozen=True)
class Stats:
    source: SourceFile
    changed_tests_per_commit: list[dict[TestFile, list[Commit]]]

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

    def substantial_change(self, commit_info) -> bool:
        if modification_map[commit_info[0]] == "A":
            return True  # always accept new files
        if commit_info is None:
            return False  # no change
        if modification_map[commit_info[0]] != "M":
            return False  # not a modification (or creation)
        if len(commit_info[1]) != 2:
            return False  # no lines added or deleted
        if commit_info[1][0] < 20 or commit_info[1][0] < commit_info[1][1]:
            return False  # not a substantial change to code
        return True

    def next_commit(self, file_number, commits: list[Commit]) -> Optional[Commit]:
        for commit in commits:
            if file_number in commit.files and self.substantial_change(
                commit.files[file_number]
            ):
                return commit
        return None

    def tfd_iterations(
        self,
        range: tuple[int, int],
        tests: set[TestFile],
    ) -> dict[TestFile, list[Commit]]:
        hits: dict[TestFile, list[Commit]] = defaultdict(list)
        for commit in self.transaction.transactions.commits[range[0] : range[1] + 1]:
            for test_file in tests:
                path = FileName(
                    os.path.join(os.path.basename(test_file.project), test_file.path)
                )
                test_id = self.transaction.mapping.name_to_id[path]
                if test_id in commit.files and self.substantial_change(
                    commit.files[test_id]
                ):
                    hits[test_file].append(commit)
                    # TODO: check coverage updates in improved version
                    # TODO: log distance from test to source file
        return hits

    @property
    def statistics(self) -> TestedFirstStatistics:
        output = []
        graph = self.file_binder.graph()
        for source_file in rich.progress.track(graph.source_files):
            if source_file not in graph.source_to_test_links:
                continue  # no tests for this source file
            path = FileName(
                os.path.join(os.path.basename(source_file.project), source_file.path)
            )
            source_id = self.transaction.mapping.name_to_id[path]
            stats = Stats(source_file, [])
            last_commit = self.transaction.transactions.commits[0]
            this_commit: Optional[Commit] = (
                self.transaction.transactions.first_occurrence(source_id)
            )
            if this_commit is None:
                continue  # never appears in the transaction log
            while (
                this_commit is not None
                and modification_map[this_commit.files[source_id][0]] != "D"
                and last_commit.number <= len(self.transaction.transactions.commits) - 1
            ):
                hits = self.tfd_iterations(
                    (last_commit.number, this_commit.number),
                    graph.source_to_test_links[source_file],
                )
                stats.changed_tests_per_commit.append(hits)
                if this_commit.number == len(self.transaction.transactions.commits) - 1:
                    break
                # find next commit with source file
                last_commit = self.transaction.transactions.commits[
                    this_commit.number + 1
                ]
                this_commit = self.next_commit(
                    source_id,
                    self.transaction.transactions.commits[this_commit.number + 1 :],
                )
            output.append(stats)
        return TestedFirstStatistics(test_statistics=output)
