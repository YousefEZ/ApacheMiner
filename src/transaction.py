import csv
import itertools
import operator
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Concatenate, NamedTuple, ParamSpec, TypeVar

import pydriller

from .driller import modification_map

P = ParamSpec("P")
T = TypeVar("T")

reverse_modification_map: dict[str, pydriller.ModificationType] = dict(
    (item[1], item[0]) for item in list(modification_map.items())
)


class TransactionMap(NamedTuple):
    ids: dict[str, int]
    names: dict[int, list[str]]


@dataclass(frozen=True)
class Transaction:
    maps: TransactionMap
    transactions: list[list[int]]


def open_as_csv(
    func: Callable[Concatenate[csv.DictReader, P], T],
) -> Callable[Concatenate[str, P], T]:
    @wraps(func)
    def wrapper(filename: str, *args: P.args, **kwargs: P.kwargs) -> T:
        with open(filename, "r") as file:
            return func(csv.DictReader(file), *args, **kwargs)

    return wrapper


@open_as_csv
def convert_into_transaction(reader: csv.DictReader) -> Transaction:
    lines = list(reader)
    commits = itertools.groupby(lines, operator.itemgetter("hash"))

    id_counter = 0
    id_map = dict()
    name_map = dict()
    transactions = []

    for _, commit in commits:
        group = list(commit)
        items = []
        for change in group:
            modification_type = pydriller.ModificationType(
                reverse_modification_map[change["modification_type"]]
            )
            if (
                modification_type == pydriller.ModificationType.ADD
                or modification_type == pydriller.ModificationType.COPY
            ):
                id = change["file"].strip()
                assert id not in id_map
                id_counter += 1
                name_map[id_counter] = [id]
                id_map[id] = id_counter
                idNum = id_counter
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.DELETE:
                id = change["file"].strip()
                assert id in id_map
                id_counter += 1
                idNum = id_map[id]
                del id_map[id]
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.MODIFY:
                id = change["file"].strip()
                assert id in id_map
                id_counter += 1
                idNum = id_map[id]
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.RENAME:
                oldId, newId = change["file"].split("|")
                assert oldId in id_map
                assert newId not in id_map
                idNum = id_map[oldId]
                del id_map[oldId]
                name_map[idNum].append(newId)
                id_map[newId] = idNum
                items.append(idNum)

        transactions.append(sorted(items))
    return Transaction(TransactionMap(id_map, name_map), transactions)


# CONVERT FOR SPM-FC-L #
def get_source_test_pairs(all_files: Iterable[tuple[int, list[str]]]) -> dict[int, str]:
    # TODO: Comprehensive (source, test) pairing - this is a temporary solution
    java_files = dict()
    pairs = dict()

    for idx, fileArr in all_files:
        path = fileArr[0].split("/")
        filename = f"{path[0]}/{path[-1]}"
        if filename.endswith(".java"):
            if filename not in java_files:
                java_files[filename] = idx

    for file in java_files:
        if file.endswith("Test.java"):
            non_test_file = file.replace("Test.java", ".java")
            if non_test_file in java_files:
                pairs[java_files[non_test_file]] = str(java_files[file])
        else:
            test_file = file.replace(".java", "Test.java")
            if test_file in java_files:
                pairs[java_files[file]] = str(java_files[test_file])

    return pairs


def convert_for_spm(in_file: str) -> tuple[list[str], TransactionMap]:
    transactions = convert_into_transaction(in_file)
    name_map = transactions.maps.names
    map_items = name_map.items()
    commits = transactions.transactions
    lines = get_source_test_pairs(map_items)

    # define various mappings for high speed lookup
    test_to_source = {int(test): source for (source, test) in lines.items()}
    for source_idx in lines:
        lines[source_idx] = ""

    # iterate over commits to fill in a line for each (source, test) pair
    for commit_no, commit in enumerate(commits, start=1):
        for file_idx in commit:
            if file_idx in lines:  # source file
                lines[file_idx] += f"<{commit_no}> {file_idx} -1 "
            if file_idx in test_to_source:  # test file
                lines[test_to_source[file_idx]] += f"<{commit_no}> {file_idx} -1 "
    for line in lines:
        lines[line] = lines[line] + "-2"
    return list(lines.values()), transactions.maps
