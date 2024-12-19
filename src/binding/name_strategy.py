from collections import defaultdict


from src.binding.strategy import BindingStrategy
from src.binding.graph import Graph
from src.binding.file_types import SourceFile, TestFile, FileName


class NameStrategy(BindingStrategy):
    """This strategy of binding is based on the name of the java files, and the test class."""

    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None:
        self._source_files = source_files
        self._test_files = test_files

    def graph(self) -> Graph:
        base_names_tests = {test_file.name: test_file for test_file in self._test_files}
        base_names_source = {
            source_file.name: source_file for source_file in self._source_files
        }

        links: dict[TestFile, set[SourceFile]] = defaultdict(set)

        for test in base_names_tests:
            if test.replace("Test", "") in base_names_source:
                links[base_names_tests[test]].add(
                    base_names_source[FileName(test.replace("Test", ""))]
                )

        return Graph(
            source_files=self._source_files, test_files=self._test_files, links=links
        )
