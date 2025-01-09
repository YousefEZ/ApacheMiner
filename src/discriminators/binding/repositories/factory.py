from typing import Type

from src.discriminators.binding.repositories.java import JavaRepository
from src.discriminators.binding.repositories.languages.factory import Languages
from src.discriminators.binding.repositories.python import PythonRepository
from src.discriminators.binding.repositories.repository import Repository

repository_factory: dict[Languages, Type[Repository]] = {
    "python": PythonRepository,
    "java": JavaRepository,
}
