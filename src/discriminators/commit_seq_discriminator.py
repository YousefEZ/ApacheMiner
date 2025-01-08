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
from .transaction import Commit, File, TransactionBuilder, TransactionLog

console = rich.console.Console()


@dataclass(frozen=True)
class Stats:
    source: SourceFile
    changed_tests_per_commit: list[dict[TestFile, list[int]]]

    @cached_property
    def is_tfd(self) -> bool:
        """Each time the source is committed, at least one test file updated
        with new methods that call to the source file"""
        for changed_tests in self.changed_tests_per_commit:
            if len(changed_tests) == 0:
                return False
        return True


@dataclass(frozen=True)
class TestedFirstStatistics(Statistics):
    test_statistics: list[Stats]
    graph: Graph

    @cached_property
    def test_first(self) -> set[SourceFile]:
        """Set of source files which are classed as having TFD"""
        return set(
            [statistic.source for statistic in self.test_statistics if statistic.is_tfd]
        )

    @cached_property
    def non_test_first(self) -> set[SourceFile]:
        """Set of source files which are classed as not having TFD"""
        return (
            set([statistic.source for statistic in self.test_statistics])
            - self.test_first
        )

    @property
    def untested_source_files(self) -> set[SourceFile]:
        return (self.graph.source_files - self.test_first) - self.non_test_first

    def output(self) -> str:
        return (
            f"Test First Updates: {len(self.test_first)}\n"
            + f"Test Elsewhere: {len(self.non_test_first)}\n"
            + f"Untested Files: {len(self.untested_source_files)}\n"
        )


@dataclass(frozen=True)
class CommitSequenceDiscriminator(Discriminator):
    commit_data: list[FileChanges]
    file_binder: BindingStrategy

    @cached_property
    def transaction(self) -> TransactionLog:
        return TransactionBuilder.build_from_groups(
            TransactionBuilder.group_file_changes(self.commit_data)
        )

    def adds_features(self, file_commit_info: File) -> bool:
        """Does this commit add new methods to the file?"""
        if file_commit_info.modification_type == ModificationType.ADD:
            return True  # auto-accept file creations
        if file_commit_info.modification_type != ModificationType.MODIFY:
            return False  # not a modification
        if len(file_commit_info.new_methods) == 0:
            return False  # not a modification with method additions
        return True

    def get_fc(self, commit: Commit, file_number: FileNumber) -> File:
        for fc in commit.files:
            if fc.file_number == file_number:
                return fc
        raise ValueError("File not found in commit")

    def next_commit(
        self, file_number: FileNumber, commits: list[Commit]
    ) -> Optional[Commit]:
        """Find the next commit which modifies the file with a feature addition"""
        for commit in commits:
            if file_number in commit.file_numbers:
                file_commit = self.get_fc(commit, file_number)
                if self.adds_features(file_commit):
                    return commit
        return None

    def tfd_iterations(
        self,
        range: tuple[int, int],
        tests: set[TestFile],
        source_name: str,
    ) -> dict[TestFile, list[int]]:
        """Within the range of commits, find the test files which are updated
        with new methods that call to the source file"""
        hits: dict[TestFile, list[int]] = defaultdict(list)
        for commit in self.transaction.transactions.commits[range[0] : range[1] + 1]:
            for test_file in tests:
                path = FileName(test_file.path)
                test_id = self.transaction.mapping.name_to_id[path]
                if test_id in commit.file_numbers:
                    file_commit = self.get_fc(commit, test_id)
                    if self.adds_features(file_commit):
                        if file_commit.modification_type == ModificationType.MODIFY:
                            if source_name in file_commit.classes_used:
                                hits[test_file].append(commit.number)
                                # test file updated with new methods and calls to source
                        else:
                            hits[test_file].append(commit.number)
                            # relevant test file ADDED
        return hits

    @property
    def statistics(self) -> TestedFirstStatistics:
        """Get set of every source file feature addition which are tested first"""
        output = []
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
            stats = Stats(source_file, [])
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
                    range=(last_commit.number, this_commit.number),
                    tests=graph.source_to_test_links[source_file],
                    source_name=source_file.name.replace(".java", ""),
                )
                stats.changed_tests_per_commit.append(hits)

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
            output.append(stats)
        return TestedFirstStatistics(test_statistics=output, graph=graph)
