from __future__ import annotations

from dataclasses import dataclass, field

from src.discriminators.binding.file_types import SourceFile, TestFile


@dataclass(frozen=True)
class Graph:
    source_files: set[SourceFile] = field(default_factory=set)
    test_files: set[TestFile] = field(default_factory=set)
    links: dict[TestFile, set[SourceFile]] = field(default_factory=dict)

    def combine(self, other: Graph):
        self.source_files.update(other.source_files)
        self.test_files.update(other.test_files)
        self.links.update(other.links)
