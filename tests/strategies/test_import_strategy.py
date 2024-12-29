import os.path
from dataclasses import dataclass
from functools import cached_property
from typing import override

from src.discriminators.binding import file_types
from src.discriminators.binding.import_strategy import ImportStrategy
from src.discriminators.binding.repository import (
    SOURCE_DIR,
    TEST_DIR,
    Files,
    Repository,
)

PROJECT_PATH = "/home/"
SOURCE_PATH = os.path.join("/home/", SOURCE_DIR, "org/package/")
TEST_PATH = os.path.join("/home/", TEST_DIR, "org/package/")


class MockRepository(Repository):
    def __init__(self, files: dict[str, Files]) -> None:
        self.files = files

    @cached_property
    def files(self) -> dict[str, Files]:
        return self.files


@dataclass(frozen=True)
class MockSourceFile(file_types.SourceFile):
    source_code: list[str]

    @override
    def get_source_code(self) -> list[str]:
        return self.source_code

    def __hash__(self) -> int:
        return super().__hash__()

    def __eq__(self, other: object) -> bool:
        return super().__eq__(other)


@dataclass(frozen=True)
class MockTestFile(file_types.TestFile):
    source_code: list[str]

    @override
    def get_source_code(self) -> list[str]:
        return self.source_code

    def __hash__(self) -> int:
        return super().__hash__()

    def __eq__(self, other: object) -> bool:
        return super().__eq__(other)


def generate_source_code(imports: list[file_types.SourceFile]) -> list[str]:
    return [f"import {ImportStrategy.import_name_of(import_)};" for import_ in imports]


def generate_source_file(name: str, source_code: list[str]) -> MockSourceFile:
    assert name.endswith(".java")
    return MockSourceFile(
        project=PROJECT_PATH,
        path=SOURCE_PATH + name,
        source_code=source_code,
    )


def generate_test_file(name: str, source_code: list[str]) -> MockTestFile:
    assert name.endswith(".java")
    return MockTestFile(
        project=PROJECT_PATH,
        path=TEST_PATH + name,
        source_code=source_code,
    )


def test_correct_import_name():
    source_file = generate_source_file("A.java", [])
    assert ImportStrategy.import_name_of(source_file) == "org.package.A"


def test_single_import_strategy():
    source_file = generate_source_file("A.java", [])
    test_file = generate_test_file("TestA.java", generate_source_code([source_file]))

    repository = MockRepository(
        files={PROJECT_PATH: Files(source_files={source_file}, test_files={test_file})}
    )
    binder = ImportStrategy(repository)

    graph = binder.graph()
    assert graph.test_files == {test_file}
    assert graph.source_files == {source_file}
    assert graph.test_to_source_links == {test_file: {source_file}}


def test_multiple_import():
    source_file = generate_source_file("A.java", [])
    source_file2 = generate_source_file("B.java", [])
    test_file = generate_test_file(
        "TestA.java", generate_source_code([source_file, source_file2])
    )

    repository = MockRepository(
        files={
            PROJECT_PATH: Files(
                source_files={source_file, source_file2}, test_files={test_file}
            )
        }
    )
    binder = ImportStrategy(repository)

    graph = binder.graph()
    assert graph.test_files == {test_file}
    assert graph.source_files == {source_file, source_file2}
    assert graph.test_to_source_links == {test_file: {source_file, source_file2}}


def test_single_import_multiple_source():
    source_file = generate_source_file("A.java", [])
    source_file2 = generate_source_file("B.java", [])
    test_file = generate_test_file("TestA.java", generate_source_code([source_file]))

    repository = MockRepository(
        files={
            PROJECT_PATH: Files(
                source_files={source_file, source_file2}, test_files={test_file}
            )
        }
    )
    binder = ImportStrategy(repository)

    graph = binder.graph()
    assert graph.test_files == {test_file}
    assert graph.source_files == {source_file, source_file2}
    assert graph.test_to_source_links == {test_file: {source_file}}


def test_single_import_multiple_test_single_source():
    source_file = generate_source_file("A.java", [])
    test_file = generate_test_file("TestA.java", generate_source_code([source_file]))
    test_file2 = generate_test_file(
        "TestAOther.java", generate_source_code([source_file])
    )

    repository = MockRepository(
        files={
            PROJECT_PATH: Files(
                source_files={source_file}, test_files={test_file, test_file2}
            )
        }
    )
    binder = ImportStrategy(repository)

    graph = binder.graph()
    assert graph.test_files == {test_file, test_file2}
    assert graph.source_files == {source_file}
    assert graph.test_to_source_links == {
        test_file: {source_file},
        test_file2: {source_file},
    }


def test_single_import_multiple_test_multiple_source():
    source_file = generate_source_file("A.java", [])
    source_file2 = generate_source_file("B.java", [])
    test_file = generate_test_file("TestA.java", generate_source_code([source_file]))
    test_file2 = generate_test_file("TestB.java", generate_source_code([source_file2]))

    repository = MockRepository(
        files={
            PROJECT_PATH: Files(
                source_files={source_file, source_file2},
                test_files={test_file, test_file2},
            )
        }
    )
    binder = ImportStrategy(repository)

    graph = binder.graph()
    assert graph.test_files == {test_file, test_file2}
    assert graph.source_files == {source_file, source_file2}
    assert graph.test_to_source_links == {
        test_file: {source_file},
        test_file2: {source_file2},
    }
