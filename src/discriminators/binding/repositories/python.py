from dataclasses import dataclass
from typing import Type, override

from src.discriminators.binding.file_types import ProgramFile
from src.discriminators.binding.repositories.repository import Repository
from src.discriminators.binding.repositories.languages.language import Language
from src.discriminators.binding.repositories.languages.python import PythonLanguage


@dataclass(frozen=True)
class PythonRepository(Repository):
    @property
    @override
    def language(self) -> Type[Language]:
        return PythonLanguage

    @override
    def is_test(self, file: ProgramFile) -> bool:
        return file.name.endswith("_test.py") or file.name.startswith("test_")
