import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import cached_property
from typing import Generator, NamedTuple, Type, TypeVar

from src.discriminators.binding.file_types import ProgramFile, SourceFile, TestFile
from src.discriminators.binding.repositories.languages.language import Language

MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"

T = TypeVar("T", bound=ProgramFile)


class Files(NamedTuple):
    source_files: set[SourceFile]
    test_files: set[TestFile]


def _all_files_in_directory(directory: str, suffix: str) -> Generator[str, None, None]:
    for root, dirnames, files in os.walk(directory):
        for dir in dirnames:
            yield from _all_files_in_directory(os.path.join(root, dir), suffix)
        for file in files:
            if file.endswith(suffix):
                yield root + os.path.sep + file


@dataclass(frozen=True)
class Repository(ABC):
    root: str

    @cached_property
    def all_files(self) -> set[ProgramFile]:
        return set(
            ProgramFile(project=self.root, path=path.replace(f"{self.root}/", ""))
            for path in _all_files_in_directory(self.root, self.language.SUFFIX)
        )

    @cached_property
    def source_files(self) -> set[SourceFile]:
        test_paths = {file.path for file in self.tests}
        return {
            SourceFile(project=file.project, path=file.path)
            for file in self.all_files
            if file.path not in test_paths
        }

    @property
    @abstractmethod
    def language(self) -> Type[Language]: ...

    @abstractmethod
    def is_test(self, file: ProgramFile) -> bool: ...

    @cached_property
    def tests(self) -> set[TestFile]:
        return {
            TestFile(project=file.project, path=file.path)
            for file in filter(self.is_test, self.all_files)
        }

    @cached_property
    def files(self) -> Files:
        return Files(source_files=self.source_files, test_files=self.tests)
