import os
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

import rich.progress
from pydriller import ModificationType

from .binding.file_types import FileName, SourceFile, TestFile
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .transaction import Commit, TransactionLog

console = rich.console.Console()


@dataclass(frozen=True)
class Stats:
    source: SourceFile
    changed_tests_per_commit: list[dict[TestFile, list[int]]]

    @cached_property
    def is_tfd(self) -> bool:
        for changed_tests in self.changed_tests_per_commit:
            if len(changed_tests) == 0:
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

    def adds_features(self, commit_info) -> bool:
        if commit_info == ModificationType.ADD:
            return True
        if commit_info is None:
            return False  # no change
        if not isinstance(commit_info, tuple):
            return False  # not a modification with method additions
        if len(commit_info[1]) == 0:
            return False  # no methods added
        return True

    def next_commit(self, file_number, commits: list[Commit]) -> Optional[Commit]:
        for commit in commits:
            if file_number in commit.files and self.adds_features(
                commit.files[file_number]
            ):
                return commit
        return None

    def tfd_iterations(
        self,
        range: tuple[int, int],
        tests: set[TestFile],
        source_name: str,
    ) -> dict[TestFile, list[int]]:
        hits: dict[TestFile, list[int]] = defaultdict(list)
        for commit in self.transaction.transactions.commits[range[0] : range[1] + 1]:
            for test_file in tests:
                path = FileName(
                    os.path.join(os.path.basename(test_file.project), test_file.path)
                )
                test_id = self.transaction.mapping.name_to_id[path]
                if test_id in commit.files and self.adds_features(
                    commit.files[test_id]
                ):
                    if isinstance(commit.files[test_id], tuple):
                        if source_name in commit.files[test_id][2]:
                            hits[test_file].append(commit.number)
                            # test file updated with new methods and calls to source
                    else:
                        hits[test_file].append(commit.number)
                        # relevant test file ADDED
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
                and this_commit.files[source_id] != ModificationType.DELETE
                and last_commit.number <= len(self.transaction.transactions.commits) - 1
            ):
                hits = self.tfd_iterations(
                    (last_commit.number, this_commit.number),
                    graph.source_to_test_links[source_file],
                    source_file.name.replace(".java", ""),
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
