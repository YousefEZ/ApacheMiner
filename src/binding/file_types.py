import os
from dataclasses import dataclass
from typing import NewType

FileName = NewType("FileName", str)


@dataclass(frozen=True)
class ProgramFile:
    project: str  # abs to repo/project
    path: str  # relative to project

    @property
    def name(self) -> FileName:
        return FileName(os.path.basename(self.path))

    def get_source_code(self) -> list[str]:
        with open(self.abs_path, "r") as file:
            return file.readlines()

    @property
    def abs_path(self) -> str:
        return os.path.join(self.project, self.path)

    def __hash__(self) -> int:
        return hash(self.abs_path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProgramFile):
            return False
        return self.abs_path == other.abs_path

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SourceFile(ProgramFile):
    pass


@dataclass(frozen=True)
class TestFile(ProgramFile):
    pass
