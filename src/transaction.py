import csv
import itertools
import operator
import statistics
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from functools import wraps
from typing import Callable, Concatenate, NamedTuple, ParamSpec, TypeVar

import pydriller
import rich.progress

from .driller import modification_map

P = ParamSpec("P")
T = TypeVar("T")

reverse_modification_map: dict[str, pydriller.ModificationType] = dict(
    (item[1], item[0]) for item in list(modification_map.items())
)


class TwoWayDict:
    def __init__(self):
        self.keys = dict()
        self.values = dict()

    def __setitem__(self, key, value):
        self.keys[key] = value
        self.values[value] = key

    def __getitem__(self, x):
        if x in self.keys:
            return self.keys[x]
        if x in self.values:
            return self.values[x]

    def get_keys(self):
        return self.keys.keys()

    def get_values(self):
        return self.values.keys()

    def __delitem__(self, x):
        if x in self.keys:
            del self.values[self.keys[x]]
            del self.keys[x]
        if x in self.values:
            del self.keys[self.values[x]]
            del self.values[x]

    def __len__(self):
        return len(self.keys)

    def __str__(self):
        return str(self.keys)

    def __contains__(self, x):
        return x in self.keys or x in self.values


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
                # id_counter += 1
                idNum = id_map[id]
                del id_map[id]
                items.append(idNum)
            elif modification_type == pydriller.ModificationType.MODIFY:
                id = change["file"].strip()
                assert id in id_map
                # id_counter += 1
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
def get_source_test_pairs(all_files: Iterable[tuple[int, list[str]]]) -> TwoWayDict:
    # TODO: Comprehensive (source, test) pairing - this is a temporary solution
    java_files = dict()
    pairs = TwoWayDict()

    for idx, fileArr in all_files:
        path = fileArr[0].split("/")
        filename = f"{path[0]}/{path[-1]}"
        if filename.endswith(".java") and filename not in java_files:
            java_files[filename] = idx

    for file in java_files:
        if file.endswith("Test.java"):
            non_test_file = file.replace("Test.java", ".java")
            if non_test_file in java_files:
                pairs[java_files[non_test_file]] = java_files[file]

    return pairs


def get_sequences(
    in_file: str, show_progress: bool
) -> tuple[dict[int, str], TransactionMap, TwoWayDict]:
    transactions = convert_into_transaction(in_file)
    name_map = transactions.maps.names
    map_items = name_map.items()
    commits = transactions.transactions
    pairs = get_source_test_pairs(map_items)
    lines: dict[int, str] = defaultdict(str)

    # iterate over commits to fill in a line for each (source, test) pair
    for commit_no, commit in wrap_iterable(enumerate(commits, start=1), show_progress):
        for file_idx in commit:
            if file_idx in pairs.get_keys():  # source file
                lines[file_idx] += format_line(commit_no, file_idx)
            elif file_idx in pairs.get_values():  # test file
                lines[pairs[file_idx]] += format_line(commit_no, file_idx)
    for file_idx in lines:
        lines[file_idx] = lines[file_idx] + "-2"
    return lines, transactions.maps, pairs


def format_line(commit_no: int, file_idx: int) -> str:
    return f"<{commit_no}> {file_idx} -1 "


def wrap_iterable(iterable: Iterable[T], show_progress: bool) -> Iterable[T]:
    return rich.progress.track(iterable) if show_progress else iterable


# PROCESS LINE BY LINE FILE COMMITS #
class TDDInfo:
    def __init__(self, source: int, test: int):
        self.source = source
        self.test = test
        self.tfd = 0.0  # % of test files that are committed before source files
        self.tdd = 0.0  # % of times source and test files are committed close together
        self.distances: list[float] = (
            []
        )  # distance between (close) source and test files

    def get_stats(self) -> tuple[float, float]:
        if len(self.distances) < 2:
            return 0, 0  # not enough data
        mean = statistics.mean(self.distances)
        confidence = 1 - (
            statistics.stdev(self.distances) / (len(self.distances) ** 0.5)
        )
        return mean, confidence

    def __str__(self) -> str:
        mean, confidence = self.get_stats()
        return (
            f"({self.source},{self.test}) "
            + f"#TFD: {round(self.tfd, 4)} #TDD: {round(self.tdd, 4)} "
            + f"#DIST: {round(mean, 4)} #CONF: {round(confidence, 4)}"
        )


def time_series_analysis(
    input_file: str, tfd_leniency: int, tdd_leniency: int, show_progress: bool
) -> tuple[list[TDDInfo], TransactionMap]:
    if show_progress:
        print("Getting sequences of source and test files...")
    sequences, name_map, pairs = get_sequences(input_file, show_progress)
    spmf = []
    if show_progress:
        print("Analyzing sequences for TFD and TDD...")
    for source, commit_info in wrap_iterable(sequences.items(), show_progress):
        spmf.append(TDDInfo(source, test=pairs[source]))
        parsed_commit_info = parse_commit_info(commit_info)
        run_analysis(spmf[-1], parsed_commit_info, tfd_leniency, tdd_leniency)
    if show_progress:
        print("Printing analysis to output file...")
    return spmf, name_map


def parse_commit_info(commit_info: str) -> list[tuple[int, int]]:
    commit_info_arr = commit_info.split(" -1 ")[:-1]
    gen_into_string = (commit.split(" ") for commit in commit_info_arr)
    return [(int(commit[0][1:-1]), int(commit[1])) for commit in gen_into_string]


def run_analysis(
    data: TDDInfo,
    commit_info: list[tuple[int, int]],
    tfd_leniency: int,
    tdd_leniency: int,
) -> None:
    source_n = 0
    test_n = 0
    tests_before_source_started = 0
    last_source = -1
    last_test = -1
    solo_commits = 0
    possible_solo = True

    for commit in commit_info:
        if commit[1] == data.source:
            if tfd_leniency == -1 and last_source == -1 and last_test == commit[0]:
                # if source & test created together, undo the special case
                tests_before_source_started -= 1
            if last_source != -1 and last_test == -1:
                solo_commits += 1
            source_n += 1
            last_source = commit[0]
        if commit[1] == data.test:
            if last_test != -1 and last_source == -1:
                solo_commits += 1
            test_n += 1
            last_test = commit[0]
            if source_n <= tfd_leniency or (
                source_n == tfd_leniency + 1 and last_source == last_test
            ):
                # committed before/with the first X source files
                tests_before_source_started += 1
            if tfd_leniency == -1 and last_source == -1:
                # special case of test before any source files
                tests_before_source_started += 1

        if last_source != -1 and last_test != -1:  # both created already
            if abs(last_source - last_test) <= tdd_leniency:
                # both files committed close together
                data.distances.append(abs(last_source - last_test))
                possible_solo = False
            else:
                if possible_solo:
                    # last commit was far away from the last
                    solo_commits += 1
                # last commit was far before this (by tdd_leniency)
                # `-> if the *next* commit is also far away, this one must be solo
                possible_solo = True

    if possible_solo:
        # account for final commit being far away from the last
        solo_commits += 1

    data.tfd = tests_before_source_started / test_n
    data.tdd = 1 - (solo_commits / len(commit_info))
