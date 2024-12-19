from dataclasses import dataclass

from src.binding.file_types import SourceFile, TestFile


@dataclass(frozen=True)
class Graph:
    source_files: set[SourceFile]
    test_files: set[TestFile]
    links: dict[TestFile, set[SourceFile]]
