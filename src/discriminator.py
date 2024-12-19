import json
import os
from dataclasses import dataclass
from typing import NewType, Optional

import rich.progress

from src.binder import Repository, SubProject
from src.binding.file_types import FileName, SourceFile, TestFile

FileNumber = NewType("FileNumber", str)


@dataclass(frozen=True)
class Commit:
    number: int
    files: list[FileNumber]


def parse_file(file: str) -> list[Commit]:
    with open(file, "r") as f:
        return [
            Commit(number, files=list(map(FileNumber, line.strip().split(" "))))
            for number, line in enumerate(f)
        ]


def get_mapping(map_file: str) -> dict[FileNumber, list[FileName]]:
    with open(map_file) as f:
        return json.load(f)


@dataclass(frozen=True)
class Transactions:
    transactions: list[Commit]
    mapping: dict[FileNumber, list[FileName]]

    def get_file_number(self, file: FileName) -> Optional[FileNumber]:
        for k, v in self.mapping.items():
            if file in v:
                return k
        return None

    def first_occurrence(self, file: FileNumber) -> Optional[Commit]:
        for commit in self.transactions:
            if file in commit.files:
                return commit
        return None


@dataclass(frozen=True)
class TestStatistics:
    test: TestFile
    before: list[SourceFile]
    after: list[SourceFile]


@dataclass(frozen=True)
class SubProjectStatistics:
    test_statistics: list[TestStatistics]

    def output_links(self):
        for statistic in self.test_statistics:
            console.print("Test: ", statistic.test.name)
            console.print(
                "Before: \n\t->", "\n\t->".join(file.name for file in statistic.before)
            )
            console.print(
                "After: \n\t->", "\n\t->".join(file.name for file in statistic.after)
            )
            console.print("[red]=== TERMINUS ===[/red]\n\n")

    def test_first_stats(self) -> tuple[int, int]:
        test_first: set[SourceFile] = set()
        test_after: set[SourceFile] = set()

        for statistic in self.test_statistics:
            test_after.update(statistic.after)
            test_first.update(statistic.before)

        actual_test_first = test_first - test_after
        return len(actual_test_first), len(test_after)


console = rich.console.Console()


@dataclass(frozen=True)
class SubProjectDiscriminator:
    transaction: Transactions
    subproject: SubProject

    @property
    def statistics(self) -> SubProjectStatistics:
        output = []
        graph = self.subproject.graph
        for test in rich.progress.track(self.subproject.tests):
            path = FileName(
                os.path.join(os.path.basename(self.subproject.path), test.path)
            )
            file_number = self.transaction.get_file_number(path)
            assert file_number is not None, f"File not found {test.name} @ {path}"
            base_commit = self.transaction.first_occurrence(file_number)
            assert base_commit
            before, after = [], []

            for source_file in graph.links[test]:
                path = FileName(
                    os.path.join(
                        os.path.basename(self.subproject.path), source_file.path
                    )
                )
                file_number = self.transaction.get_file_number(path)
                assert (
                    file_number is not None
                ), f"File not found {source_file.name} @ {path}"
                commit = self.transaction.first_occurrence(file_number)
                assert commit
                if commit.number < base_commit.number:
                    before.append(source_file)
                else:
                    after.append(source_file)
            if before or after:
                output.append(TestStatistics(test, before, after))
        return SubProjectStatistics(test_statistics=output)


@dataclass(frozen=True)
class Discriminator:
    transaction: Transactions
    repository: Repository


if __name__ == "__main__":
    repo = Repository(os.path.abspath("../zookeeper"))
    for subproject in repo.subprojects:
        logs = parse_file("transactions.txt")
        mapping = get_mapping("mapping.json")

        transactions = Transactions(logs, mapping)
        subproject_discriminator = SubProjectDiscriminator(transactions, subproject)

        print(f"Analyzing subproject: {subproject.path}")
        print(subproject_discriminator.statistics.test_first_stats())
