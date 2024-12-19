from typing import Protocol


from src.binding.graph import Graph
from src.binding.file_types import SourceFile, TestFile


class BindingStrategy(Protocol):
    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None: ...

    def graph(self) -> Graph: ...
