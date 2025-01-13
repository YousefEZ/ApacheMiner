from __future__ import annotations

import itertools
import operator
from functools import cached_property
from typing import Callable, NamedTuple, Optional, Self

import pydriller
from pydantic import BaseModel

from src.discriminators.align import CommitAligner
from src.discriminators.binding.file_types import FileName
from src.discriminators.file_types import FileChanges, FileNumber

modification_map: dict[pydriller.ModificationType, str] = {
    pydriller.ModificationType.ADD: "A",
    pydriller.ModificationType.COPY: "C",
    pydriller.ModificationType.DELETE: "D",
    pydriller.ModificationType.MODIFY: "M",
    pydriller.ModificationType.RENAME: "R",
    pydriller.ModificationType.UNKNOWN: "U",
}


reverse_modification_map: dict[str, pydriller.ModificationType] = dict(
    (item[1], item[0]) for item in list(modification_map.items())
)


def logstr_to_set(string: str) -> set[str]:
    string = string.strip().removeprefix("{").removesuffix("}")
    strings = string.split(",")
    for s in range(len(strings)):
        strings[s] = strings[s].strip().removeprefix("'").removesuffix("'")
    return set(strings)


class FileChange(BaseModel):
    file_number: FileNumber
    modification_type: pydriller.ModificationType
    new_methods: set[str]
    classes_used: set[str]

    def __lt__(self, other: FileChange) -> bool:
        return self.file_number < other.file_number

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FileChange):
            return NotImplemented
        return self.file_number == other.file_number


class Commit(BaseModel):
    number: int
    files: list[FileChange]

    @property
    def file_numbers(self) -> list[FileNumber]:
        return [file.file_number for file in self.files]


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
            if file_number in commit.file_numbers:
                return commit
        return None


class TransactionBuilderResult(NamedTuple):
    transactions: Transactions
    mapping: TransactionMap


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
            pydriller.ModificationType, Callable[[FileChanges], Optional[FileChange]]
        ] = {
            pydriller.ModificationType.ADD: self._add,
            pydriller.ModificationType.COPY: self._copy,
            pydriller.ModificationType.DELETE: self._delete,
            pydriller.ModificationType.MODIFY: self._modify,
            pydriller.ModificationType.RENAME: self._rename,
            pydriller.ModificationType.UNKNOWN: self._unknown,
        }
        self._commit_number = 0

    @staticmethod
    def group_file_changes(
        changes: list[FileChanges],
    ) -> list[tuple[str, list[FileChanges]]]:
        return [
            (commit, list(changes))
            for commit, changes in itertools.groupby(
                changes, operator.itemgetter("hash")
            )
        ]

    @staticmethod
    def build_from_groups(
        commits: list[tuple[str, list[FileChanges]]],
    ) -> TransactionLog:
        builder = TransactionBuilder()
        for _, changes in commits:
            builder.process(changes)
        result = builder.build()
        return TransactionLog(transactions=result.transactions, mapping=result.mapping)

    def process(self, commit: list[FileChanges]):
        items: list[FileChange] = []
        for file in commit:
            if not file["file"]:
                continue  # empty commit

            modification_type = reverse_modification_map[file["modification_type"]]
            item = self._mapping[modification_type](file)
            if item:
                items.append(item)
        if not items:
            return
        self._transactions.append(
            Commit(number=self._commit_number, files=sorted(items))
        )
        self._commit_number += 1

    def _unknown(self, _: FileChanges) -> None:
        return None

    def _delete(self, _: FileChanges) -> FileChange | None:
        return None

    def _add(self, file: FileChanges) -> FileChange:
        file_name: FileName = FileName(file["file"].strip())
        if file_name in self._id_map:
            return self._modify(file)
        self._id_counter = FileNumber(1 + self._id_counter)
        self._name_map[self._id_counter] = [file_name]
        self._id_map[file_name] = self._id_counter
        return FileChange(
            file_number=self._id_counter,
            modification_type=pydriller.ModificationType.ADD,
            new_methods=set(),
            classes_used=set(),
        )

    def _modify(self, file: FileChanges) -> FileChange:
        file_name: FileName = FileName(file["file"].strip())
        new_methods = set(file["new_methods"].split("|"))
        classes_used = set(file["classes_used"].split("|"))
        if file_name not in self._id_map:
            return self._add(file)
        return FileChange(
            file_number=self._id_map[file_name],
            modification_type=pydriller.ModificationType.MODIFY,
            new_methods=new_methods,
            classes_used=classes_used,
        )

    def _rename(self, file: FileChanges) -> FileChange:
        old_name, new_name = map(FileName, file["file"].strip().split("|"))
        if old_name not in self._id_map:
            self._add({**file, "file": old_name})
        file_number = self._id_map[old_name]
        self._name_map[file_number].append(new_name)
        self._id_map[new_name] = file_number
        return FileChange(
            file_number=file_number,
            modification_type=pydriller.ModificationType.MODIFY,
            new_methods=set(),
            classes_used=set(),
        )

    def _copy(self, file: FileChanges) -> FileChange:
        file_name: FileName = FileName(file["file"].strip())
        self._id_counter = FileNumber(1 + self._id_counter)
        self._name_map[self._id_counter] = [file_name]
        self._id_map[file_name] = self._id_counter
        return FileChange(
            file_number=self._id_counter,
            modification_type=pydriller.ModificationType.MODIFY,
            new_methods=set(),
            classes_used=set(),
        )

    def build(self) -> TransactionBuilderResult:
        return TransactionBuilderResult(
            transactions=Transactions(commits=self._transactions),
            mapping=TransactionMap(id_to_names=self._name_map),
        )


class TransactionLog(BaseModel):
    transactions: Transactions
    mapping: TransactionMap

    @classmethod
    def aligned_commit_log(cls, rows: list[FileChanges]) -> Self:
        commits = itertools.groupby(rows, operator.itemgetter("hash"))
        aligner = CommitAligner(
            [(commit, list(changes)) for commit, changes in commits]
        )
        return cls.build_transactions_from_groups(list(aligner))

    @classmethod
    def build_transactions_from_groups(cls, commits: list[list[FileChanges]]) -> Self:
        builder = TransactionBuilder()
        for changes in commits:
            builder.process(changes)

        result = builder.build()
        return cls(transactions=result.transactions, mapping=result.mapping)

    @classmethod
    def from_commit_log(cls, rows: list[FileChanges]) -> Self:
        commits = itertools.groupby(rows, operator.itemgetter("hash"))
        return cls.build_transactions_from_groups(
            [list(changes) for _, changes in commits]
        )
