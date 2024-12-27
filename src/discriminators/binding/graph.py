from __future__ import annotations

from dataclasses import dataclass, field

from src.discriminators.binding.file_types import ProgramFile, SourceFile, TestFile


@dataclass(frozen=True)
class Graph:
    source_files: set[SourceFile] = field(default_factory=set)
    test_files: set[TestFile] = field(default_factory=set)
    links: dict[ProgramFile, set[ProgramFile]] = field(default_factory=dict)

    def combine(self, other: Graph):
        self.source_files.update(other.source_files)
        self.test_files.update(other.test_files)
        self.links.update(other.links)

    def diff(self, other: Graph) -> Graph:
        source_files = self.source_files.symmetric_difference(other.source_files)
        test_files = self.test_files.symmetric_difference(other.test_files)
        links = {
            k: v.symmetric_difference(other.links[k])
            for k, v in self.links.items()
            if k in other.links and v.symmetric_difference(other.links[k])
        }

        links.update({k: v for k, v in self.links.items() if k not in other.links})
        links.update({k: v for k, v in other.links.items() if k not in self.links})
        return Graph(source_files, test_files, links)
