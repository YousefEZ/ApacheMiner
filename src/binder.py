from __future__ import annotations

from collections import defaultdict
from typing import Optional, Protocol, Type
import os
from dataclasses import dataclass
from functools import cached_property, lru_cache
from typing import Generator, NewType

import rich.progress
import matplotlib.pyplot as plt
import networkx as nx

FileName = NewType("FileName", str)

MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"


console = rich.console.Console()


@dataclass(frozen=True)
class Graph:
    source_files: set[SourceFile]
    test_files: set[TestFile]
    links: dict[TestFile, set[SourceFile]]


class BindingStrategy(Protocol):
    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None: ...

    def graph(self) -> Graph: ...


class ImportStrategy(BindingStrategy):
    """This strategy of binding is based on the import statements in the java files."""

    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None:
        self._source_files = source_files
        self._test_files = test_files

    def import_name_of(self, java_file: JavaFile) -> str:
        directories = java_file.abs_path.split(os.path.sep)
        for idx, subdirectory in enumerate(directories):
            if subdirectory == "java":
                break
        else:
            raise ValueError(f"Cannot find java directory in {java_file.abs_path}")
        return ".".join(directories[idx + 1 :]).replace(".java", "")

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


@dataclass(frozen=True)
class JavaFile:
    project: str  # abs to repo/project
    path: str  # relative to project

    def __repr__(self) -> str:
        return self.name

    @property
    def name(self) -> FileName:
        return FileName(os.path.basename(self.path))

    @property
    def abs_path(self) -> str:
        return self.project + "/" + self.path

    def __hash__(self) -> int:
        return hash(self.abs_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JavaFile):
            return False
        return self.abs_path == other.abs_path


@dataclass(frozen=True)
class SourceFile(JavaFile):
    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class TestFile(JavaFile):
    def __repr__(self) -> str:
        return self.name

    def __hash__(self) -> int:
        return hash(self.abs_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JavaFile):
            return False
        return self.abs_path == other.abs_path


def files_from_directory(directory: str) -> Generator[str, None, None]:
    for root, dirnames, files in os.walk(directory):
        for dir in dirnames:
            yield from files_from_directory(f"{root}/{dir}")
        for file in files:
            if file.endswith(".java"):
                yield root + "/" + file


class SubProject:
    def __init__(self, path: str, strategy: Type[BindingStrategy]):
        self.path = path
        self.strategy = strategy

    @cached_property
    def graph(self) -> Graph:
        return self.strategy(self.source_files, self.tests).graph()

    @staticmethod
    def is_project(path: str) -> bool:
        return all(
            os.path.exists(f"{path}/{sub_path}") for sub_path in (SOURCE_DIR, TEST_DIR)
        )

    @cached_property
    def tests(self) -> set[TestFile]:
        return {
            TestFile(
                project=self.path,
                path=path.replace(f"{self.path}/", ""),
            )
            for path in files_from_directory(f"{self.path}/{TEST_DIR}")
        }

    @cached_property
    def source_files(self) -> set[SourceFile]:
        files = {
            SourceFile(
                project=self.path,
                path=path.replace(f"{self.path}/", ""),
            )
            for path in files_from_directory(f"{self.path}/{SOURCE_DIR}")
        }
        return files


@dataclass(frozen=True)
class Repository:
    root: str

    @cached_property
    def subprojects(self) -> set[SubProject]:
        return {
            SubProject(f"{self.root}/{path}", strategy=NameStrategy)
            for path in os.listdir(self.root)
            if SubProject.is_project(f"{self.root}/{path}")
        }


if __name__ == "__main__":
    repository = Repository(os.path.abspath("../flink"))

    graph = nx.DiGraph()

    project = next(iter(repository.subprojects))
    print(f"Displaying links for project: {project.path}")
    for source_file in project.source_files:
        graph.add_node(f"Source: {source_file.name}", type="source")

    project_graph = project.graph
    for test in project.tests:
        test_node = f"Test: {test.name}"
        graph.add_node(test_node, type="test")

        for source_file in project.graph.links[test]:
            source_node = f"Source: {source_file.name}"
            graph.add_edge(test_node, source_node)

    pos = nx.spring_layout(graph)
    plt.figure(figsize=(12, 8))

    test_nodes = [
        node for node, data in graph.nodes(data=True) if data["type"] == "test"
    ]
    source_nodes = [
        node for node, data in graph.nodes(data=True) if data["type"] == "source"
    ]

    nx.draw_networkx_nodes(
        graph, pos, nodelist=test_nodes, node_color="red", label="Test Files"
    )
    nx.draw_networkx_nodes(
        graph, pos, nodelist=source_nodes, node_color="blue", label="Source Files"
    )
    nx.draw_networkx_edges(graph, pos)
    nx.draw_networkx_labels(graph, pos, font_size=10, font_color="black")

    plt.legend()
    plt.title("Test-to-Source Links")
    plt.show()
