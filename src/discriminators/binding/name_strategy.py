from collections import defaultdict
from dataclasses import dataclass

from .file_types import FileName, ProgramFile
from .graph import Graph
from .repository import Repository
from .strategy import BindingStrategy


@dataclass(frozen=True)
class NameStrategy(BindingStrategy):
    """This strategy of binding is based on the name of the java files,
    and the test class."""

    repository: Repository

    def _graph_generator(self) -> Graph:
        base_names_tests = {
            test_file.name: test_file
            for files in self.repository.files.values()
            for test_file in files.test_files
        }
        base_names_source = {
            source_file.name: source_file
            for files in self.repository.files.values()
            for source_file in files.source_files
        }

        links: dict[ProgramFile, set[ProgramFile]] = defaultdict(set)

        for test in base_names_tests:
            if test.replace("Test", "") in base_names_source:
                links[base_names_tests[test]].add(
                    base_names_source[FileName(test.replace("Test", ""))]
                )
                links[base_names_source[FileName(test.replace("Test", ""))]].add(
                    base_names_tests[test]
                )

        return Graph(
            source_files=set(base_names_source.values()),
            test_files=set(base_names_tests.values()),
            links=links,
        )

    def graph(self) -> Graph:
        return self._graph_generator()
