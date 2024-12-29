from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from src.discriminators.binding.file_types import SourceFile, TestFile


@dataclass(frozen=True)
class Graph:
    source_files: set[SourceFile] = field(default_factory=set)
    test_files: set[TestFile] = field(default_factory=set)
    test_to_source_links: dict[TestFile, set[SourceFile]] = field(default_factory=dict)

    def combine(self, other: Graph):
        self.source_files.update(other.source_files)
        self.test_files.update(other.test_files)
        self.test_to_source_links.update(other.test_to_source_links)

    def diff(self, other: Graph) -> Graph:
        source_files = self.source_files.symmetric_difference(other.source_files)
        test_files = self.test_files.symmetric_difference(other.test_files)
        links = {
            k: v.symmetric_difference(other.test_to_source_links[k])
            for k, v in self.test_to_source_links.items()
            if k in other.test_to_source_links
            and v.symmetric_difference(other.test_to_source_links[k])
        }

        links.update(
            {
                k: v
                for k, v in self.test_to_source_links.items()
                if k not in other.test_to_source_links
            }
        )
        links.update(
            {
                k: v
                for k, v in other.test_to_source_links.items()
                if k not in self.test_to_source_links
            }
        )
        return Graph(source_files, test_files, links)

    @property
    def source_to_test_links(self) -> dict[SourceFile, set[TestFile]]:
        links: dict[SourceFile, set[TestFile]] = defaultdict(set)
        for test, sources in self.test_to_source_links.items():
            for source in sources:
                links[source].add(test)
        return links
