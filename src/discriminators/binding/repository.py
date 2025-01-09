from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from typing import Generator, NamedTuple, Protocol, TypeVar

from src.discriminators.binding.file_types import ProgramFile, SourceFile, TestFile

MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"

T = TypeVar("T", bound=ProgramFile)


class Repository(Protocol):
    @cached_property
    def files(self) -> Files: ...


class Files(NamedTuple):
    source_files: set[SourceFile]
    test_files: set[TestFile]


def _all_files_in_directory(directory: str) -> Generator[str, None, None]:
    for root, dirnames, files in os.walk(directory):
        for dir in dirnames:
            yield from _all_files_in_directory(os.path.join(root, dir))
        for file in files:
            if file.endswith(".java"):
                yield root + os.path.sep + file


@dataclass(frozen=True)
class JavaRepository(Repository):
    root: str

    @cached_property
    def all_files(self) -> set[ProgramFile]:
        return set(
            ProgramFile(project=self.root, path=path.replace(f"{self.root}/", ""))
            for path in _all_files_in_directory(self.root)
        )

    @cached_property
    def source_files(self) -> set[SourceFile]:
        test_paths = {file.path for file in self.tests}
        return {
            SourceFile(project=file.project, path=file.path)
            for file in self.all_files
            if file.path not in test_paths
        }

    def is_test(self, file: ProgramFile) -> bool:
        for line in file.get_source_code():
            if "@Test" in line:
                return True
        return False
        
    @cached_property
    def tests(self) -> set[TestFile]:
        return {
            TestFile(project=file.project, path=file.path)
            for file in filter(self.is_test, self.all_files)
        }

    @cached_property
    def files(self) -> Files:
        return Files(source_files=self.source_files, test_files=self.tests)
