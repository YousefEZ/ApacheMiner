import json
from dataclasses import dataclass
from functools import cached_property
from itertools import groupby
from typing import Optional, Self

import rich.progress

from src.discriminators.binding.file_types import SourceFile
from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.discriminator import Discriminator, Statistics
from src.discriminators.file_types import FileChanges
from src.discriminators.transaction import (
    TransactionBuilder,
    TransactionLog,
    TransactionMap,
    Transactions,
)

console = rich.console.Console()


@dataclass(frozen=True)
class CommitNode:
    hash: str
    changes: list[FileChanges]
    parents: list[Self]


@dataclass(frozen=True)
class Branch:
    head: CommitNode
    tail: CommitNode

    @cached_property
    def commits(self) -> set[str]:
        node = self.tail
        commits = {self.head.hash}
        while node.hash != self.head.hash:
            commits.add(node.hash)
            node = node.parents[0]
        return commits

    def make_log(self) -> TransactionLog:
        builder = TransactionBuilder()
        node = self.tail
        changes = []
        while node.hash != self.head.hash:
            changes.append(node.changes)
            node = node.parents[0]
        changes.append(node.changes)
        for change in reversed(changes):
            builder.process(change)
        results = builder.build()
        return TransactionLog(
            transactions=results.transactions, mapping=results.mapping
        )


class CommitLog:
    def __init__(self, changes: list[tuple[str, list[FileChanges]]]):
        # TODO: restructure such that init doesn't contain logic
        self._commits = changes
        self._nodes: dict[str, CommitNode] = {}
        self._main_branch = self._make_tree()

    def _locate_changes(self, commit_hash: str) -> list[FileChanges]:
        for idx in range(len(self._commits)):
            if self._commits[idx][0] == commit_hash:
                return self._commits[idx][1]
        raise ValueError(f"Commit with hash {commit_hash} not found")

    def _create_commit_from_changes(
        self,
        commit_hash: str,
        changes: Optional[list[FileChanges]] = None,
    ):
        """Creates a commit from the changes given

        Args:
            commit_hash (str): The hash of the commit
            changes (list[FileChanges]): The changes to create the commit from

        """
        if commit_hash in self._nodes:
            return self._nodes[commit_hash]

        if changes is None:
            changes = self._locate_changes(commit_hash)

        parents_hash = changes[0]["parents"].split("|")
        parents: list[CommitNode] = []

        if changes[0]["parents"]:
            for parent_hash in parents_hash:
                if parent_hash not in self._nodes:
                    self._create_commit_from_changes(parent_hash)
                parents.append(self._nodes[parent_hash])

        self._nodes[commit_hash] = CommitNode(commit_hash, changes, parents)

    def _make_tree(self) -> Branch:
        """Creates a branch from the commits given, assuming all the commits
        eventually lead to the commit containing 0 parents to the last commit that
        contains no children

        Args:
            commits (list[tuple[str, list[FileChanges]]]): The commits to create
                    the branch from

        Returns (Branch): The branch created from the commits given
        """

        for idx in range(len(self._commits)):
            self._create_commit_from_changes(
                self._commits[idx][0], self._commits[idx][1]
            )

        assert (
            self._nodes[self._commits[0][0]].parents == []
        ), "The first commit should have no parents"

        return Branch(
            head=self._nodes[self._commits[0][0]],
            tail=self._nodes[self._commits[-1][0]],
        )

    def trace_path_back_to_main(self, tail: CommitNode) -> Branch:
        """Traces the path back to the main branch

        Args:
            tail (CommitNode): The tail of the branch to trace back to main

        Returns (Branch): The branch that was traced back to main

        Example:

            B----->C----->D---->E
            ^                   |
            |                   v
            W-------->X-------->Y----->Z

            Where E is the arg tail then the result is a branch with the head
            at B and the tail at E
        """
        node = tail
        while node.parents[0].hash not in self._main_branch.commits:
            node = node.parents[0]
        return Branch(node, tail)

    def get_successor(self, node: CommitNode) -> Optional[CommitNode]:
        current_node = self._main_branch.tail
        successor = None
        while current_node.hash != node.hash:
            successor = current_node
            current_node = current_node.parents[0]
        return successor

    def all_merge_branches_into_main(self) -> list[Branch]:
        branches = []
        current_node = self._main_branch.tail
        while current_node.hash != self._main_branch.head.hash:
            if len(current_node.parents) == 2:
                branch = self.trace_path_back_to_main(current_node.parents[1])
                branches.append(branch)
            current_node = current_node.parents[0]
        return branches


@dataclass(frozen=True)
class BranchResults:
    branch: Branch
    before: set[SourceFile]
    after: set[SourceFile]
    untested: set[SourceFile]


@dataclass(frozen=True)
class BranchStatistics(Statistics):
    results: list[BranchResults]

    def output(self) -> str:
        return "\n".join(
            f"Branch: {result.branch.head.hash} -> {result.branch.tail.hash}\n"
            + f"Before: {len(result.before)}\n"
            + f"After: {len(result.after)}\n"
            + f"Untested: {len(result.untested)}\n"
            for result in self.results
        )


@dataclass(frozen=True)
class BranchDiscriminator(Discriminator):
    transaction: TransactionLog
    file_binder: BindingStrategy
    commit_data: list[FileChanges]

    def process_branch(self, branch: Branch) -> BranchResults: ...

    @property
    def statistics(self) -> BranchStatistics:
        graph = self.file_binder.graph()
        print(f"Graph has {len(graph.test_files)} test files")
        print(f"Graph has {len(graph.source_files)} source files")
        print(f"Graph has {len(graph.links)} links")
        log = CommitLog(
            [
                (commit_hash, list(changes))
                for commit_hash, changes in groupby(
                    self.commit_data, lambda x: x["hash"]
                )
            ]
        )
        branches = log.all_merge_branches_into_main()
        stats = list(map(self.process_branch, branches))

        return BranchStatistics(results=stats)


if __name__ == "__main__":
    with open("transactions.txt") as t, open("mapping.json") as m:
        transactions = Transactions.model_validate(json.load(t))
        mapping = TransactionMap.model_validate(json.load(m))

    transaction_log = TransactionLog(transactions=transactions, mapping=mapping)
