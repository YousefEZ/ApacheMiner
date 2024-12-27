import os
from dataclasses import dataclass, field
from typing import NewType

FileName = NewType("FileName", str)


@dataclass(frozen=True)
class ProgramFile:
    project: str = field(compare=False, hash=False)  # abs to repo/project
    path: str = field(compare=True, hash=True)  # relative to project

    @property
    def name(self) -> FileName:
        return FileName(os.path.basename(self.path))

    def get_source_code(self) -> list[str]:
        with open(self.abs_path, "r") as file:
            return file.readlines()

    @property
    def abs_path(self) -> str:
        return os.path.join(self.project, self.path)

    def __repr__(self) -> str:
        return self.name


@dataclass(frozen=True)
class SourceFile(ProgramFile):
    pass


@dataclass(frozen=True)
class TestFile(ProgramFile):
    pass
