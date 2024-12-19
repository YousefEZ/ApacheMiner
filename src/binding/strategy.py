from typing import Protocol

from src.binding.file_types import SourceFile, TestFile
from src.binding.graph import Graph


class BindingStrategy(Protocol):
    def __init__(
        self, source_files: set[SourceFile], test_files: set[TestFile]
    ) -> None: ...

    def graph(self) -> Graph: ...
