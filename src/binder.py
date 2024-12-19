from __future__ import annotations

import os
from dataclasses import dataclass
from functools import cached_property
from typing import Generator, Type, TypeVar

import matplotlib.pyplot as plt
import networkx as nx
import rich.progress

from src.binding.file_types import JavaFile, SourceFile, TestFile
from src.binding.graph import Graph
from src.binding.import_strategy import ImportStrategy
from src.binding.strategy import BindingStrategy

MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"

T = TypeVar("T", bound=JavaFile)

console = rich.console.Console()


def _all_files_in_directory(directory: str) -> Generator[str, None, None]:
    for root, dirnames, files in os.walk(directory):
        for dir in dirnames:
            yield from _all_files_in_directory(f"{root}/{dir}")
        for file in files:
            if file.endswith(".java"):
                yield root + os.path.sep + file


@dataclass(frozen=True)
class SubProject:
    path: str
    strategy: Type[BindingStrategy]

    @cached_property
    def graph(self) -> Graph:
        return self.strategy(self.source_files, self.tests).graph()

    @staticmethod
    def is_project(path: str) -> bool:
        return all(
            os.path.exists(f"{path}/{sub_path}") for sub_path in (SOURCE_DIR, TEST_DIR)
        )

    def _fetch_files_from_directory(
        self, file_type: Type[T], subdirectory: str
    ) -> set[T]:
        return {
            file_type(
                project=self.path,
                path=path.replace(f"{self.path}/", ""),
            )
            for path in _all_files_in_directory(f"{self.path}/{subdirectory}")
        }

    @cached_property
    def tests(self) -> set[TestFile]:
        return self._fetch_files_from_directory(TestFile, TEST_DIR)

    @cached_property
    def source_files(self) -> set[SourceFile]:
        return self._fetch_files_from_directory(SourceFile, SOURCE_DIR)


@dataclass(frozen=True)
class Repository:
    root: str

    @cached_property
    def subprojects(self) -> set[SubProject]:
        return {
            SubProject(f"{self.root}/{path}", strategy=ImportStrategy)
            for path in os.listdir(self.root)
            if SubProject.is_project(f"{self.root}/{path}")
        }


def visualize_project(project: SubProject):
    graph = nx.DiGraph()

    for source_file in project.source_files:
        graph.add_node(f"Source: {source_file.name}", type="source")

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


if __name__ == "__main__":
    repository = Repository(os.path.abspath("../flink"))
    project = next(iter(repository.subprojects))
    visualize_project(project)
