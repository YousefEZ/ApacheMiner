import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional, override

import rich.progress

from src.discriminators.binding.file_types import ProgramFile, SourceFile
from src.discriminators.binding.graph import Graph
from src.discriminators.binding.repositories.repository import RepositoryProtocol
from src.discriminators.binding.strategy import BindingStrategy


@dataclass(frozen=True)
class ImportStrategy(BindingStrategy):
    """This strategy of binding is based on the import statements in the java files."""

    repository: RepositoryProtocol

    @lru_cache
    def fetch_links(self, file: ProgramFile) -> set[SourceFile]:
        links: set[SourceFile] = set()
        for source_file in self.repository.files.source_files:
            if self.repository.language.import_name_of(
                source_file
            ) in self.repository.language.fetch_import_names(file):
                links.add(source_file)
        return links

    def graph(self) -> Graph:
        files = self.repository.files
        links = {
            test_file: self.fetch_links(test_file)
            for test_file in rich.progress.track(files.test_files, "Creating links...")
        }

        logging.info(
            "Unable to find links for the following files:"
            + os.linesep
            + os.linesep.join([str(file) for file, link in links.items() if not link])
        )

        return Graph(
            source_files=files.source_files,
            test_files=files.test_files,
            test_to_source_links=links,
        )


class RecursiveImportStrategy(ImportStrategy):
    @override
    @lru_cache
    def fetch_links(self, java_file: ProgramFile) -> set[SourceFile]:
        return self.recursive_links(java_file)

    def recursive_links(
        self, target: ProgramFile, visited: Optional[set[SourceFile]] = None
    ) -> set[SourceFile]:
        if visited is None:
            visited = set()
        links: set[SourceFile] = super().fetch_links(target).copy()
        for link in list(filter(lambda file_link: file_link not in visited, links)):
            visited.add(link)
            links.update(self.recursive_links(link, visited))

        return links
