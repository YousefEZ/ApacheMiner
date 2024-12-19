import os
from functools import lru_cache
from typing import Optional

import rich.progress

from src.binding.file_types import JavaFile, SourceFile, TestFile
from src.binding.graph import Graph
from src.binding.strategy import BindingStrategy


class ImportStrategy(BindingStrategy):
    """This strategy of binding is based on the import statements in the java files."""

    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None:
        self._source_files = source_files
        self._test_files = test_files

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
        assert all(file.project == java_file.project for file in self._source_files)
        links: set[SourceFile] = set()
        for source_file in self._source_files:
            if self.import_name_of(source_file) in self.fetch_import_names(java_file):
                links.add(source_file)
        return links

    def graph(self) -> Graph:
        links = {
            test_file: self.fetch_links(test_file)
            for test_file in rich.progress.track(
                self._test_files, "Creating links for tests..."
            )
        }
        return Graph(
            source_files=self._source_files, test_files=self._test_files, links=links
        )


class RecursiveImportStrategy(ImportStrategy):
    def recursive_links(
        self, target: JavaFile, visited: Optional[set[SourceFile]] = None
    ) -> set[SourceFile]:
        if visited is None:
            visited = set()
        links: set[SourceFile] = self.fetch_links(target).copy()
        for link in self.fetch_links(target):
            if link in visited:
                continue
            visited.add(link)
            links.update(self.recursive_links(link, visited))

        return links

    def graph(self) -> Graph:
        links = {
            test_file: self.recursive_links(test_file)
            for test_file in rich.progress.track(
                self._test_files, "Creating links for tests..."
            )
        }
        return Graph(
            source_files=self._source_files, test_files=self._test_files, links=links
        )
