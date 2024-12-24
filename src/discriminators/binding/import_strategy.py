import os
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from typing import Generator, Optional, override

import rich.progress

from .file_types import ProgramFile
from .graph import Graph
from .repository import Repository
from .strategy import BindingStrategy


@dataclass(frozen=True)
class ImportStrategy(BindingStrategy):
    """This strategy of binding is based on the import statements in the java files."""

    repository: Repository

    @staticmethod
    def import_name_of(java_file: ProgramFile) -> str:
        directories = java_file.abs_path.split(os.path.sep)
        for idx, subdirectory in enumerate(directories, start=1):
            if subdirectory == "java":
                break
        else:
            raise ValueError(f"Cannot find java directory in {java_file.abs_path}")

        return ".".join(directories[idx:]).replace(".java", "")

    @lru_cache
    def fetch_import_names(self, java_file: ProgramFile) -> set[str]:
        imports: set[str] = set()
        for line in java_file.get_source_code():
            if line.startswith("import"):
                imports.add(line.replace("import ", "").replace(";", "").strip())
            elif "class" in line:
                break
        return imports

    @lru_cache
    def fetch_links(self, java_file: ProgramFile) -> set[ProgramFile]:
        links: set[ProgramFile] = set()
        for source_file in self.repository.files[java_file.project].source_files:
            if self.import_name_of(source_file) in self.fetch_import_names(java_file):
                links.add(source_file)
        return links

    def _graph_generator(self) -> Generator[Graph, None, None]:
        for i, files in enumerate(self.repository.files.values()):
            links: dict[ProgramFile, set[ProgramFile]] = defaultdict(set)
            for test_file in rich.progress.track(
                files.test_files,
                f"Creating links #{i}...",
            ):
                links[test_file] = self.fetch_links(test_file)
                for source_file in links[test_file]:
                    links[source_file].add(test_file)

            yield Graph(
                source_files=files.source_files,
                test_files=files.test_files,
                links=links,
            )

    def graph(self) -> Graph:
        graph = Graph()
        for subgraph in self._graph_generator():
            graph.combine(subgraph)
        return graph


class RecursiveImportStrategy(ImportStrategy):
    @override
    @lru_cache
    def fetch_links(self, java_file: ProgramFile) -> set[ProgramFile]:
        return self.recursive_links(java_file)

    def recursive_links(
        self, target: ProgramFile, visited: Optional[set[ProgramFile]] = None
    ) -> set[ProgramFile]:
        if visited is None:
            visited = set()
        links: set[ProgramFile] = super().fetch_links(target).copy()
        for link in self.fetch_links(target):
            if link in visited:
                continue
            visited.add(link)
            links.update(self.recursive_links(link, visited))

        return links
