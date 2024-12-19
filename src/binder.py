from __future__ import annotations

from typing import Generator
from dataclasses import dataclass
from functools import cached_property
import os

import networkx as nx
import matplotlib.pyplot as plt


MAIN = "main"
SOURCE_DIR = "src/main/java"
TEST_DIR = "src/test/java"


@dataclass(frozen=True)
class JavaFile:
    project: str  # abs to repo/project
    path: str  # relative to project

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    @property
    def project_path(self) -> str:
        directories = self.abs_path.split(os.path.sep)
        for idx, subdirectory in enumerate(directories):
            if subdirectory == MAIN:
                break
        else:
            return ""
        return "/".join(directories[idx:])

    @property
    def import_name(self) -> str:
        directories = self.abs_path.split(os.path.sep)
        for idx, subdirectory in enumerate(directories):
            if subdirectory == "java":
                break
        else:
            raise ValueError(f"Cannot find java directory in {self.abs_path}")
        return ".".join(directories[idx + 1 :]).replace(".java", "")

    @property
    def abs_path(self) -> str:
        return self.project + "/" + self.path

    @cached_property
    def imports(self) -> list[str]:
        with open(self.abs_path, "r") as file:
            lines = file.readlines()
            return [
                line.replace("import ", "").replace(";", "").strip()
                for line in lines
                if line.startswith("import")
            ]

    def fetch_links(self, source_files: set[SourceFile]) -> set[SourceFile]:
        assert all(file.project == self.project for file in source_files)
        links: set[SourceFile] = set()
        for source_file in source_files:
            if source_file.import_name in self.imports:
                links.add(source_file)
                if isinstance(self, SourceFile):
                    links.update(source_file.fetch_links(source_files - {self}))
                else:
                    links.update(source_file.fetch_links(source_files))
        return links

    def __hash__(self) -> int:
        return hash(self.abs_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, JavaFile):
            return False
        return self.abs_path == other.abs_path


@dataclass(frozen=True)
class SourceFile(JavaFile): ...


@dataclass(frozen=True)
class TestFile(JavaFile):
    links: set[SourceFile]

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


@dataclass(frozen=True)
class SubProject:
    path: str  # abs to repo/project

    @staticmethod
    def is_project(path: str) -> bool:
        return all(
            os.path.exists(f"{path}/{sub_path}") for sub_path in (SOURCE_DIR, TEST_DIR)
        )

    @cached_property
    def tests(self) -> set[TestFile]:
        test_files = {
            JavaFile(project=self.path, path=path.replace(f"{self.path}/", ""))
            for path in files_from_directory(f"{self.path}/{TEST_DIR}")
        }

        return {
            TestFile(
                project=self.path,
                path=test_file.path,
                links=test_file.fetch_links(self.source_files),
            )
            for test_file in test_files
        }

    @cached_property
    def source_files(self) -> set[SourceFile]:
        files = {
            SourceFile(project=self.path, path=path.replace(f"{self.path}/", ""))
            for path in files_from_directory(f"{self.path}/{SOURCE_DIR}")
        }
        return files


@dataclass(frozen=True)
class Repository:
    root: str

    @cached_property
    def subprojects(self) -> set[SubProject]:
        return {
            SubProject(f"{self.root}/{path}")
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
    for test in project.tests:
        test_node = f"Test: {test.name}"
        graph.add_node(test_node, type="test")

        for source_file in test.links:
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
