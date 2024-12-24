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


# TODO: Add tests
