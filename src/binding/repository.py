from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from typing import Generator, NamedTuple, Protocol, Type, TypeVar

from src.binding.file_types import ProgramFile, SourceFile, TestFile

MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"

T = TypeVar("T", bound=ProgramFile)


class Repository(Protocol):
    @cached_property
    def files(self) -> dict[str, Files]: ...


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
class JavaSubProject:
    path: str

    @staticmethod
    def is_project(path: str) -> bool:
        return all(
            os.path.exists(os.path.join(path, sub_path))
            for sub_path in (SOURCE_DIR, TEST_DIR)
        )

    def _fetch_files_from_directory(
        self, file_type: Type[T], subdirectory: str
    ) -> set[T]:
        return {
            file_type(
                project=self.path,
                path=path.replace(f"{self.path}/", ""),
            )
            for path in _all_files_in_directory(os.path.join(self.path, subdirectory))
        }

    @cached_property
    def tests(self) -> set[TestFile]:
        return self._fetch_files_from_directory(TestFile, TEST_DIR)

    @cached_property
    def source_files(self) -> set[SourceFile]:
        return self._fetch_files_from_directory(SourceFile, SOURCE_DIR)


@dataclass(frozen=True)
class JavaRepository(Repository):
    root: str

    @cached_property
    def subprojects(self) -> set[JavaSubProject]:
        return {
            JavaSubProject(os.path.join(self.root, path))
            for path in os.listdir(self.root)
            if JavaSubProject.is_project(os.path.join(self.root, path))
        }

    @cached_property
    def files(self) -> dict[str, Files]:
        return {
            project.path: Files(
                project.source_files,
                project.tests,
            )
            for project in self.subprojects
        }
