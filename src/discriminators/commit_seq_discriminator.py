from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from typing import Optional

import rich.progress
from pydriller import ModificationType

from src.discriminators.binding.graph import Graph

from .binding.file_types import FileName, SourceFile, TestFile
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .file_types import FileChanges, FileNumber
from .transaction import Commit, CommitFileChange, TransactionBuilder, TransactionLog

console = rich.console.Console()


@dataclass(frozen=True)
class Stats:
    changed_tests_per_commit: dict[int, dict[TestFile, list[int]]]

    @cached_property
    def tfd_count(self) -> int:
        return sum(
            bool(self.changed_tests_per_commit[commit])
            for commit in self.changed_tests_per_commit
        )

    def is_tfd(self, threshold: float) -> bool:
        """Each time the source is committed, at least one test file updated
        with new methods that call to the source file"""
        if not self.changed_tests_per_commit:
            return False
        return self.tfd_count / len(self.changed_tests_per_commit) >= threshold

    def same_commit(self) -> float:
        """Percentage of test files updated in the same commit as the source"""
        assert self.tfd_count, "is_tfd called first"
        same_commit = 0
        for commit_no in self.changed_tests_per_commit:
            for test_file in self.changed_tests_per_commit[commit_no]:
                if commit_no in self.changed_tests_per_commit[commit_no][test_file]:
                    same_commit += 1
                    break
        return same_commit / self.tfd_count


@dataclass(frozen=True)
class TestedFirstStatistics(Statistics):
    test_statistics: dict[SourceFile, Stats]
    graph: Graph

    def test_first(self, threshold: float) -> set[SourceFile]:
        """Set of source files which are classed as having TFD"""
        return {
            statistic
            for statistic in self.test_statistics.keys()
            if self.test_statistics[statistic].is_tfd(threshold)
        }

    def non_test_first(self, threshold: float) -> set[SourceFile]:
        """Set of source files which are classed as not having TFD"""
        return {
            statistic for statistic in self.test_statistics.keys()
        } - self.test_first(threshold)

    @property
    def untested_source_files(self) -> set[SourceFile]:
        return {source_file for source_file in self.graph.source_files} - {
            statistic for statistic in self.test_statistics.keys()
        }

    def same_commit_count(self, tfd_files: set[SourceFile]) -> int:
        """Percentage of test files updated in the same commit as the source"""
        if len(tfd_files) == 0:
            return 0
        same_commit: float = 0
        for source_file in tfd_files:
            source_statistic = self.test_statistics[source_file]
            same_commit += source_statistic.same_commit()
        return int((same_commit / len(tfd_files)) * 100)

    def output(self) -> str:
        thresholds = (1.0, 0.75, 0.5)
        string = ""
        for threshold in thresholds:
            test_first = self.test_first(threshold)
            string += (
                f"Threshold: {threshold}\n"
                f"Test First Updates: {len(test_first)}\n"
                + f"Test Elsewhere: {len(self.non_test_first(threshold))}\n"
                + f"Same Commit: {self.same_commit_count(test_first)}%\n"
            )
        return string + f"Untested Files: {len(self.untested_source_files)}"


@dataclass(frozen=True)
class CommitSequenceDiscriminator(Discriminator):
    commit_data: list[FileChanges]
    file_binder: BindingStrategy

    @cached_property
    def transaction(self) -> TransactionLog:
        return TransactionBuilder.build_from_groups(
            TransactionBuilder.group_file_changes(self.commit_data)
        )

    def adds_features(self, file_commit_info: CommitFileChange) -> bool:
        """Does this commit add new methods to the file?"""
        if file_commit_info.modification_type == ModificationType.ADD:
            return True  # auto-accept file creations
        if file_commit_info.modification_type != ModificationType.MODIFY:
            return False  # not a modification
        if len(file_commit_info.new_methods) == 0:
            return False  # not a modification with method additions
        return True

    def get_fc(self, commit: Commit, file_number: FileNumber) -> CommitFileChange:
        for fc in commit.files:
            if fc.file_number == file_number:
                return fc
        raise ValueError("File not found in commit")

    def next_commit(
        self, file_number: FileNumber, commits: list[Commit]
    ) -> Optional[Commit]:
        """Find the next commit which modifies the file with a feature addition"""
        for commit in commits:
            if file_number not in commit.file_numbers:
                continue

            file_commit = self.get_fc(commit, file_number)
            if self.adds_features(file_commit):
                return commit
        return None

    def tfd_iterations(
        self,
        commit_range: tuple[int, int],
        tests: set[TestFile],
    ) -> dict[TestFile, list[int]]:
        """Within the range of commits, find the test files which are updated
        with new methods that call to the source file"""
        hits: dict[TestFile, list[int]] = defaultdict(list)
        for commit in self.transaction.transactions.commits[
            commit_range[0] : commit_range[1] + 1
        ]:
            for test_file in tests:
                path = FileName(test_file.path)
                test_id = self.transaction.mapping.name_to_id[path]
                if test_id not in commit.file_numbers:
                    continue

                file_commit = self.get_fc(commit, test_id)
                if not self.adds_features(file_commit):
                    continue

                hits[test_file].append(commit.number)
        return hits

    @property
    def statistics(self) -> TestedFirstStatistics:
        """Get set of every source file feature addition which are tested first"""
        output = {}
        graph = self.file_binder.graph()
        print(f"Graph has {len(graph.test_files)} test files")
        print(f"Graph has {len(graph.source_files)} source files")
        print(f"Graph has {len(graph.test_to_source_links)} links")
        commit_count = len(self.transaction.transactions.commits)
        for source_file in rich.progress.track(graph.source_files):
            # setup the source file for tracking
            if source_file not in graph.source_to_test_links:
                continue
            path = FileName(source_file.path)
            source_id = self.transaction.mapping.name_to_id[path]
            stats = Stats({})
            last_commit = self.transaction.transactions.commits[0]
            this_commit: Optional[Commit] = (
                self.transaction.transactions.first_occurrence(source_id)
            )
            if this_commit is None:
                continue

            # until the file is deleted or the last commit is reached
            while (
                this_commit is not None
                and self.get_fc(this_commit, source_id).modification_type
                != ModificationType.DELETE
                and last_commit.number <= commit_count - 1
            ):
                # find test files updated with new methods calling to the source file
                hits = self.tfd_iterations(
                    commit_range=(last_commit.number, this_commit.number),
                    tests=graph.source_to_test_links[source_file],
                )
                stats.changed_tests_per_commit[this_commit.number] = hits

                # setup next iteration with the next time this source file is committed
                if this_commit.number == commit_count - 1:
                    break
                last_commit = self.transaction.transactions.commits[
                    this_commit.number + 1
                ]
                this_commit = self.next_commit(
                    source_id,
                    self.transaction.transactions.commits[this_commit.number + 1 :],
                )
            output[source_file] = stats
        return TestedFirstStatistics(test_statistics=output, graph=graph)
