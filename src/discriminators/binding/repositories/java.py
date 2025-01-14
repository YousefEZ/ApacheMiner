from dataclasses import dataclass
from typing import Type, override

from src.discriminators.binding.file_types import ProgramFile
from src.discriminators.binding.repositories.languages.java import JavaLanguage
from src.discriminators.binding.repositories.languages.language import Language
from src.discriminators.binding.repositories.repository import Repository


@dataclass(frozen=True)
class JavaRepository(Repository):
    @property
    @override
    def language(self) -> Type[Language]:
        return JavaLanguage

    @override
    def is_test(self, file: ProgramFile) -> bool:
        for line in file.get_source_code():
            if "@Test" in line:
                return True
        return False
