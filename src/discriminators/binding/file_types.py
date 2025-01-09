import os
from dataclasses import dataclass, field
from functools import cached_property
from typing import NewType

import chardet

FileName = NewType("FileName", str)


@dataclass(frozen=True)
class ProgramFile:
    project: str = field(compare=False, hash=False)  # abs to repo/project
    path: str = field(compare=True, hash=True)  # relative to project

    @property
    def name(self) -> FileName:
        return FileName(os.path.basename(self.path))

    @cached_property
    def encoding(self) -> str:
        with open(self.abs_path, "rb") as file:
            raw_data = file.read()
            result = chardet.detect(raw_data)
            encoding = result["encoding"]
            assert encoding is not None
            return encoding

    def _read_source_code(self, encoding="utf-8") -> list[str]:
        with open(self.abs_path, "r", encoding=encoding) as file:
            return file.readlines()

    def get_source_code(self) -> list[str]:
        try:
            return self._read_source_code()
        except UnicodeError:
            return self._read_source_code(encoding=self.encoding)

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
