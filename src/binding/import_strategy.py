import os
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Generator, Optional, override

import rich.progress

from src.binding._repository import JavaRepository
from src.binding.file_types import JavaFile, SourceFile
from src.binding.graph import Graph
from src.binding.strategy import BindingStrategy


@dataclass(frozen=True)
class ImportStrategy(BindingStrategy):
    """This strategy of binding is based on the import statements in the java files."""

    path: str

    @cached_property
    def repository(self) -> JavaRepository:
        return JavaRepository(self.path)

    def import_name_of(self, java_file: JavaFile) -> str:
        directories = java_file.abs_path.split(os.path.sep)
        for idx, subdirectory in enumerate(directories, start=1):
            if subdirectory == "java":
                break
        else:
            raise ValueError(f"Cannot find java directory in {java_file.abs_path}")

        return ".".join(directories[idx:]).replace(".java", "")

    @lru_cache
    def fetch_import_names(self, java_file: JavaFile) -> set[str]:
        with open(java_file.abs_path, "r") as file:
            imports: set[str] = set()
            while line := file.readline():
                if line.startswith("import"):
                    imports.add(line.replace("import ", "").replace(";", "").strip())
                elif "class" in line:
                    break
            return imports

    @lru_cache
    def fetch_links(self, java_file: JavaFile) -> set[SourceFile]:
        links: set[SourceFile] = set()
        for source_file in self.repository.files[java_file.project].source_files:
            if self.import_name_of(source_file) in self.fetch_import_names(java_file):
                links.add(source_file)
        return links

    def _graph_generator(self) -> Generator[Graph, None, None]:
        for files in self.repository.files.values():
            links = {
                test_file: self.fetch_links(test_file)
                for test_file in rich.progress.track(
                    files.test_files, "Creating links for tests..."
                )
            }
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
    def fetch_links(self, java_file: JavaFile) -> set[SourceFile]:
        return self.recursive_links(java_file)

    def recursive_links(
        self, target: JavaFile, visited: Optional[set[SourceFile]] = None
    ) -> set[SourceFile]:
        if visited is None:
            visited = set()
        links: set[SourceFile] = super().fetch_links(target).copy()
        for link in self.fetch_links(target):
            if link in visited:
                continue
            visited.add(link)
            links.update(self.recursive_links(link, visited))

        return links
