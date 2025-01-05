from __future__ import annotations

import itertools
import operator
from dataclasses import dataclass
from functools import cached_property
from typing import Callable, Iterator, NamedTuple, NewType, Optional, Self, TypedDict

import pydriller
from pydantic import BaseModel

from src.discriminators.binding.file_types import FileName

FileNumber = NewType("FileNumber", int)

modification_map: dict[pydriller.ModificationType, str] = {
    pydriller.ModificationType.ADD: "A",
    pydriller.ModificationType.COPY: "C",
    pydriller.ModificationType.DELETE: "D",
    pydriller.ModificationType.MODIFY: "M",
    pydriller.ModificationType.RENAME: "R",
}


reverse_modification_map: dict[str, pydriller.ModificationType] = dict(
    (item[1], item[0]) for item in list(modification_map.items())
)


class Commit(BaseModel):
    number: int
    files: list[FileNumber]


class TransactionMap(BaseModel):
    id_to_names: dict[FileNumber, list[FileName]]

    @cached_property
    def name_to_id(self) -> dict[FileName, FileNumber]:
        return {
            FileName(name): FileNumber(k)
            for k, v in self.id_to_names.items()
            for name in v
        }


class Transactions(BaseModel):
    commits: list[Commit]

    def first_occurrence(self, file_number: FileNumber) -> Optional[Commit]:
        for commit in self.commits:
            if file_number in commit.files:
                return commit
        return None


class SerializedTransactionLog(TypedDict):
    transactions: str
    mapping: str


class FileChanges(TypedDict):
    hash: str
    modification_type: str
    file: str
    parents: str


class TransactionBuilderResult(NamedTuple):
    transactions: Transactions
    mapping: TransactionMap


@dataclass
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
        commits = set()
        while node.hash != self.head.hash:
            commits.add(node.hash)
            node = node.parents[0]
        return commits


class CommitAligner:
    """
    Inlines the branches into the main branch, so that the main branch
    contains all the changes from the other branches. This is done by
    tracing the path back to the main branch and then stitching the branch
    into the main branch. So that the main branch has no branches and all
    commits are ordered in terms of when they were commited into the main
    branch

    Example:

               F-------->G-------->H
               ^                   |
               |                   |
        B----->C----->D---->E      |
        ^                   |      |
        |                   v      v
        W-------->X-------->Y----->Z


        becomes W-->X-->B-->C-->D-->E-->Y-->F-->G-->H-->Z
    """

    def __init__(self, changes: list[tuple[str, list[FileChanges]]]):
        self._changes = changes
        self._main_branch = self._make_main_branch(self._changes)
        self._inline_branches()

    def _make_main_branch(self, commits: list[tuple[str, list[FileChanges]]]) -> Branch:
        nodes: dict[str, CommitNode] = dict()

        for commit_hash, commit in commits:
            changes: list[FileChanges] = list(commit)
            parents = [nodes[parent] for parent in changes[0]["parents"].split(",")]
            nodes[commit_hash] = CommitNode(
                hash=commit_hash, changes=changes, parents=parents
            )

        return Branch(head=nodes[commits[0][0]], tail=nodes[commits[-1][0]])

    def _trace_path_back_to_main(self, tail: CommitNode) -> Branch:
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

    def _stitch_path(self, node: CommitNode, path: Branch, visited: set[str]) -> Branch:
        """Stitches the branch into the node given


        Example:

            B----->C----->D---->E
            ^                   |
            |                   V
            W-------->X-------->Y----->Z

            Attaching the path B-->C-->D-->E results in


            W-->X-->B-->C-->D-->E-->Y-->Z
        """
        branch_node = path.tail
        branch_node_previous = node
        while branch_node.hash not in visited:
            branch_node_previous = branch_node
            branch_node = branch_node.parents[0]

        # make the start of the branch have the parent of the merge
        branch_node_previous.parents[0] = node.parents[0]

        # Removing the main branch parent and replacing it with branch tail
        node.parents = [path.tail]

        return Branch(node, path.tail)

    def _inline_branches(self):
        """Inlines the branches by finding each merge commit, tracing the path
        back to where it checks out from main, and stitching the branch.
        After stitching it goes back to start of the branch and finds the next
        merge commit, therefore any branching off the branch is also inlined
        """
        visited = set()
        current_node = self._main_branch.head
        while current_node is not None:
            visited.add(current_node.hash)
            if len(current_node.parents) != 2:
                # we only want the merge commits
                continue

            path = self._trace_path_back_to_main(current_node.parents[1])

            stitched_branch = self._stitch_path(current_node, path, visited)
            visited.update(stitched_branch.commits)

            # go back to the start of the branch
            current_node = stitched_branch.head

    def __iter__(self) -> Iterator[list[FileChanges]]:
        """Converts the branches into rows of FileChanges"""
        rows = []
        current_node = self._main_branch.tail
        while current_node is not None:
            for change in current_node.changes:
                rows.append(change)
            current_node = current_node.parents[0] if current_node.parents else None
        return reversed(rows)


class TransactionBuilder:
    """A class to build a TransactionLog from a list of FileChanges, which is based
    off the the algorithm provided in the lecture with a few modifications to account
    for merges"""

    def __init__(self: Self):
        self._id_counter: FileNumber = FileNumber(0)
        self._id_map: dict[FileName, FileNumber] = dict()
        self._name_map: dict[FileNumber, list[FileName]] = dict()
        self._transactions: list[Commit] = []
        self._mapping: dict[
            pydriller.ModificationType, Callable[[FileName], FileNumber]
        ] = {
            pydriller.ModificationType.ADD: self._add,
            pydriller.ModificationType.COPY: self._copy,
            pydriller.ModificationType.DELETE: self._delete,
            pydriller.ModificationType.MODIFY: self._modify,
            pydriller.ModificationType.RENAME: self._rename,
        }
        self._commit_number = 0

    def process(self, commit: list[FileChanges]) -> None:
        items: list[FileNumber] = []
        for file in commit:
            modification_type = reverse_modification_map[file["modification_type"]]
            file_name: FileName = FileName(file["file"].strip())
            self._mapping[modification_type](file_name)
        self._transactions.append(
            Commit(number=self._commit_number, files=sorted(items))
        )
        self._commit_number += 1

    def _add(self, file_name: FileName) -> FileNumber:
        assert file_name not in self._id_map
        self._id_counter = FileNumber(1 + self._id_counter)
        self._name_map[self._id_counter] = [file_name]
        self._id_map[file_name] = self._id_counter
        return self._id_counter

    def _delete(self, file_name: FileName) -> FileNumber:
        assert file_name in self._id_map
        self._id_counter = FileNumber(1 + self._id_counter)
        del self._id_map[file_name]
        return self._id_map[file_name]

    def _modify(self, file_name: FileName) -> FileNumber:
        assert file_name in self._id_map
        self._id_counter = FileNumber(1 + self._id_counter)
        return self._id_map[file_name]

    def _rename(self, file_name: FileName) -> FileNumber:
        oldId, newId = map(FileName, file_name.split("|"))
        assert oldId in self._id_map
        assert newId not in self._id_map
        idNum = self._id_map[oldId]
        del self._id_map[oldId]
        self._name_map[idNum].append(newId)
        self._id_map[newId] = idNum
        return idNum

    def _copy(self, file_name: FileName) -> FileNumber:
        self._id_counter = FileNumber(1 + self._id_counter)
        self._id_map[file_name] = self._id_counter
        self._name_map[self._id_counter] = [file_name]
        return self._id_counter

    def build(self) -> TransactionBuilderResult:
        return TransactionBuilderResult(
            transactions=Transactions(commits=self._transactions),
            mapping=TransactionMap(id_to_names=self._name_map),
        )


class TransactionLog(BaseModel):
    transactions: Transactions
    mapping: TransactionMap

    def filter_on(self, filterer: Callable[[FileName], bool]) -> TransactionLog:
        """Removes anything that does pass the filterer, and creates a new
        TransactionLog without these entries

        Args:
            filterer (Callable[[FileName], bool]): The filterer which takes
            the file_name as an argument

        Returns (TransactionLog): The new TransactionLog with the filtered
            entries
        """
        removed_ids = {
            id
            for id, names in self.mapping.id_to_names.items()
            if not filterer(names[-1])
        }

        mapping = {
            id: names
            for id, names in self.mapping.id_to_names.items()
            if id not in removed_ids
        }
        commit_id = 0
        commits: list[Commit] = []
        for commit in self.transactions.commits:
            new_files = [file for file in commit.files if file not in removed_ids]
            if not new_files:
                continue

            commits.append(Commit(number=commit_id, files=new_files))
            commit_id += 1
        return TransactionLog(
            transactions=Transactions(commits=commits),
            mapping=TransactionMap(id_to_names=mapping),
        )

    @classmethod
    def from_commit_data(cls, rows: list[dict[str, str]]) -> Self:
        """Parses the rows of dict[col, val] to provide a TransactionLog

        Args:
            rows (list[dict[str, str]]): The rows of data to parse

        Return TransactionLog: The parsed transaction log
        """
        commits = itertools.groupby(rows, operator.itemgetter("hash"))

        id_counter: FileNumber = FileNumber(0)
        id_map: dict[FileName, FileNumber] = dict()
        name_map: dict[FileNumber, list[FileName]] = dict()
        transactions: list[Commit] = []

        commit_number = -1
        for commit_hash, commit in commits:
            commit_number += 1
            group: list[dict[str, str]] = list(commit)
            items: list[FileNumber] = []
            for change in group:
                modification_type = reverse_modification_map[
                    change["modification_type"]
                ]

                file_name: FileName = FileName(change["file"].strip())

                if (
                    modification_type == pydriller.ModificationType.ADD
                    or modification_type == pydriller.ModificationType.COPY
                ):
                    assert file_name not in id_map
                    id_counter = FileNumber(1 + id_counter)
                    name_map[id_counter] = [file_name]
                    id_map[file_name] = id_counter
                    idNum = id_counter
                    items.append(idNum)
                elif modification_type == pydriller.ModificationType.DELETE:
                    assert file_name in id_map
                    id_counter = FileNumber(1 + id_counter)
                    idNum = id_map[file_name]
                    del id_map[file_name]
                    items.append(idNum)
                elif modification_type == pydriller.ModificationType.MODIFY:
                    assert file_name in id_map
                    id_counter = FileNumber(1 + id_counter)
                    idNum = id_map[file_name]
                    items.append(idNum)
                elif modification_type == pydriller.ModificationType.RENAME:
                    oldId, newId = map(FileName, change["file"].split("|"))
                    assert oldId in id_map
                    assert newId not in id_map
                    idNum = id_map[oldId]
                    del id_map[oldId]
                    name_map[idNum].append(newId)
                    id_map[newId] = idNum
                    items.append(idNum)

            transactions.append(Commit(number=commit_number, files=sorted(items)))

        return cls(
            transactions=Transactions(commits=transactions),
            mapping=TransactionMap(id_to_names=name_map),
        )

    @classmethod
    def aligned_commit_log(cls, rows: list[FileChanges]) -> Self:
        commits = itertools.groupby(rows, operator.itemgetter("hash"))
        aligner = CommitAligner(
            [(commit, list(changes)) for commit, changes in commits]
        )
        return cls.new_from_commit_data(list(aligner))

    @classmethod
    def new_from_commit_data(cls, commits: list[list[FileChanges]]) -> Self:
        builder = TransactionBuilder()
        for changes in commits:
            builder.process(changes)

        result = builder.build()
        return cls(transactions=result.transactions, mapping=result.mapping)

    @classmethod
    def new_from_rows(cls, rows: list[FileChanges]) -> Self:
        commits = itertools.groupby(rows, operator.itemgetter("hash"))
        builder = TransactionBuilder()
        for _, commit in commits:
            builder.process(list(commit))

        result = builder.build()
        return cls(transactions=result.transactions, mapping=result.mapping)
