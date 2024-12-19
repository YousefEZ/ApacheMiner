import os
from dataclasses import dataclass
from typing import NewType

FileName = NewType("FileName", str)


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
