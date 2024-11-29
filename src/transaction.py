import csv
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Concatenate, NamedTuple, ParamSpec, TypeVar
import itertools

from .driller import modification_map

import pydriller


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
    mapper: TransactionMap
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
def convert_drilled_into_transaction(reader: csv.DictReader) -> Transaction:
    lines = list(reader)
    commits = list(itertools.groupby(lines, key=lambda line: line["hash"]))

    id_counter = 0
    id_map = dict()
    name_map = dict()
    items = list()
    transactions = []

    for _, commit in commits:
        for change in commit:
            modification_type = pydriller.ModificationType(
                reverse_modification_map[change["modification_type"]]
            )
            if modification_type == pydriller.ModificationType.ADD:
                # Added file, is not allowed to exist already
                id = change["file"].strip()
                assert id not in id_map
                id_counter += 1
                name_map[id_counter] = [id]
                id_map[id] = id_counter
                idNum = id_counter
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.DELETE:
                # Deleted file, must exist already
                id = change["file"].strip()
                assert id in id_map
                id_counter += 1
                idNum = id_map[id]
                del id_map[id]
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.MODIFY:
                # Changed file, must exist already
                id = change["file"].strip()
                assert id in id_map
                id_counter += 1
                idNum = id_map[id]
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.RENAME:
                # Renamed file, old must exist already and new is not allowed to exist already.
                oldId, newId = change["file"].split("|")
                assert oldId in id_map
                assert newId not in id_map
                idNum = id_map[oldId]
                del id_map[oldId]
                name_map[idNum].append(newId)
                id_map[newId] = idNum
                items.append(idNum)
            else:
                # Something else, should be the commit id and message.
                # Write current set and start new set
                transactions.append(" ".join(map(str, sorted(items))))
                items.clear()
    transactions.append(" ".join(map(str, sorted(items))))

    return Transaction(TransactionMap(id_map, name_map), transactions)
