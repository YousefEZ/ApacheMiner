from functools import lru_cache
from typing import Optional, Protocol

from src.discriminators.binding.file_types import ProgramFile


class Language(Protocol):
    SUFFIX: str

    @staticmethod
    def get_defined_method(line: str) -> Optional[str]: ...

    @staticmethod
    def get_classes_used(diffs: dict[str, list[tuple[int, str]]]) -> set[str]: ...

    @staticmethod
    @lru_cache
    def import_name_of(file: ProgramFile) -> Optional[str]: ...

    @staticmethod
    @lru_cache
    def fetch_import_names(java_file: ProgramFile) -> set[str]: ...
