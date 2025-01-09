from typing import Literal, Type, cast

from github import Github

from src.discriminators.binding.repositories.languages.java import JavaLanguage
from src.discriminators.binding.repositories.languages.language import Language
from src.discriminators.binding.repositories.languages.python import PythonLanguage

Languages = Literal["java", "python"]


language_factory: dict[Languages, Type[Language]] = {
    "java": JavaLanguage,
    "python": PythonLanguage,
}


def get_repository_language(repository: str) -> Languages:
    """Get the language of the repository


    Args:
        repository (str): The repository name in the form org/name

    Returns (str): The language of the repository
    """

    github = Github()
    repo = github.get_repo(repository)
    return cast(Languages, repo.language.lower())
