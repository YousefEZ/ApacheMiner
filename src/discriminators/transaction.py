from __future__ import annotations

import itertools
import operator
from functools import cached_property
from typing import Callable, NewType, Optional, Self, TypedDict

import pydriller

from src.discriminators.binding.file_types import FileName

from pydantic import BaseModel

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
