from __future__ import annotations

import os
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Literal, Optional, ParamSpec, Sequence, TypeVar, cast

import pydriller
import rich.progress
from dotenv import load_dotenv
from github import Auth, Github
from github.Commit import Commit
from github.File import File
from github.PullRequest import PullRequest
from github.Repository import Repository
from pydriller import ModificationType

from src.custom_types.commit import CommitProtocol, ModifiedFileProtocol

__all__ = ("get_squash_merges", "expand_squash_merge")


T = TypeVar("T")
P = ParamSpec("P")

GitModificationType = Literal[
    "added", "removed", "modified", "renamed", "copied", "changed", "unchanged"
]

change_type_mapping: dict[GitModificationType, ModificationType] = {
    "added": ModificationType.ADD,
    "removed": ModificationType.DELETE,
    "modified": ModificationType.MODIFY,
    "renamed": ModificationType.RENAME,
    "copied": ModificationType.COPY,
    "changed": ModificationType.UNKNOWN,
    "unchanged": ModificationType.UNKNOWN,
}


@dataclass(frozen=True)
class ChangedFile(ModifiedFileProtocol):
    _change_type: pydriller.ModificationType
    _old_path: Optional[str]
    _new_path: Optional[str]
    _patch: Optional[str] = None

    @property
    def change_type(self) -> pydriller.ModificationType:
        return self._change_type

    @property
    def old_path(self) -> Optional[str]:
        return self._old_path

    @property
    def new_path(self) -> Optional[str]:
        return self._new_path

    @property
    def diff_parsed(self) -> dict[str, list[tuple[int, str]]]:
        """This method is lifted from pydriller.ModifiedFile so that it achieves
        parity


        Returns (dict[str, list[tuple[int, str]]]): A dictionary with two keys:
        """
        modified_lines: dict[str, list[tuple[int, str]]] = {
            "added": [],
            "deleted": [],
        }
        if not self._patch:
            return modified_lines

        lines = self._patch.split("\n")
        count_deletions = 0
        count_additions = 0

        for line in lines:
            line = line.rstrip()
            count_deletions += 1
            count_additions += 1

            if line.startswith("@@"):
                count_deletions, count_additions = self._get_line_numbers(line)

            if line.startswith("-"):
                modified_lines["deleted"].append((count_deletions, line[1:]))
                count_additions -= 1

            if line.startswith("+"):
                modified_lines["added"].append((count_additions, line[1:]))
                count_deletions -= 1

            if line == r"\ No newline at end of file":
                count_deletions -= 1
                count_additions -= 1

        return modified_lines

    @staticmethod
    def _get_line_numbers(line: str) -> tuple[int, int]:
        token = line.split(" ")
        numbers_old_file = token[1]
        numbers_new_file = token[2]
        delete_line_number = int(numbers_old_file.split(",")[0].replace("-", "")) - 1
        additions_line_number = int(numbers_new_file.split(",")[0]) - 1
        return delete_line_number, additions_line_number


@dataclass(frozen=True)
class UnSquashedCommit(CommitProtocol):
    _modified_files: list[ChangedFile]
    _hash: str
    _parents: list[str]

    @property
    def modified_files(self) -> Sequence[ChangedFile]:
        return self._modified_files

    @property
    def hash(self) -> str:
        return self._hash

    @property
    def parents(self) -> list[str]:
        return self._parents


def singleton(function: Callable[P, T]) -> Callable[P, T]:
    """A decorator that makes the result of a function (T) a singleton

    Args:
        function (Callable[[], T]): A function that returns an object T

    Returns (Callable[[], T]): A function only executed once for the
        same arguments (persistent cache)
    """
    instances: dict[Any, T] = dict()

    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        nonlocal instances
        if args not in instances:
            instances[args] = function(*args, **kwargs)
        return instances[args]

    return wrapper


@singleton
def get_github() -> Github:
    """Returns a singleton Github object with the given token

    Returns (Github): A Github object
    """
    load_dotenv()

    TOKEN = os.getenv("GITHUB_TOKEN")
    assert TOKEN is not None, "GITHUB_TOKEN environment variable is not set"

    return Github(
        auth=Auth.Token(TOKEN),
        per_page=100,
        pool_size=15,
        retry=None,
        seconds_between_requests=0,
        seconds_between_writes=0,
    )


@singleton
def get_repository(org: str, name: str) -> Repository:
    """Gets a repository by its organization and name

    Args:
        org (str): The organization name
        name (str): The repository name

    Returns (Repository): A repository object
    """
    return get_github().get_repo(f"{org}/{name}")


def get_squash_merges(
    org: str, name: str, progress: Optional[rich.progress.Progress] = None
) -> frozenset[PullRequest]:
    """Gets all squash merges from a repository, by fetching all closed pull requests
    and filtering out merged pull requests that have a different merge commit sha
    than the head sha.

    Args:
        org (str): The organization name
        name (str): The repository name

    Returns (frozenset[PullRequest]): A set of pull requests that were squash merged
    """
    if progress is None:
        progress = rich.progress.Progress()
    repository = get_repository(org, name)
    pull_requests = repository.get_pulls(state="closed", base=repository.default_branch)

    return frozenset(
        pull
        for pull in progress.track(
            pull_requests,
            total=pull_requests.totalCount,
            description="Fetching Squash Merges...",
        )
        if pull.merged_at is not None and pull.merge_commit_sha != pull.head.sha
    )


def convert_pygithub_file(file: File) -> ChangedFile:
    """Converts a PyGitHub File object to a ChangedFile object, as extra
    checks need to be carried out to ensure the correct layout of data

    Args:
        file (File): A PyGitHub File object

    Returns (ChangedFile): A ChangedFile object
    """
    change_type = change_type_mapping[cast(GitModificationType, file.status)]
    if change_type == ModificationType.DELETE:
        return ChangedFile(
            _change_type=change_type, _old_path=file.filename, _new_path=None
        )
    return ChangedFile(
        _change_type=change_type,
        _old_path=file.previous_filename,
        _new_path=file.filename,
        _patch=(
            file.patch if file.sha is not None else None
        ),  # if permission change then no patch
    )


def transform_to_unsquashed_commit(commit: Commit) -> UnSquashedCommit:
    """Analyzes the commit, by extracting the required infromation to
    generate a UnSquashedCommit object that abides by the CommitProtocol

    Args:
        commit (Commit): A commit object from PyGitHub

    Returns (UnSquashedCommit): A UnSquashedCommit object
    """
    return UnSquashedCommit(
        _modified_files=[convert_pygithub_file(file) for file in commit.files],
        _hash=commit.sha,
        _parents=[parent.sha for parent in commit.parents],
    )


def expand_squash_merge(squash_merge: PullRequest) -> list[UnSquashedCommit]:
    """Expands a squash merge by extracting all the commits that were squashed

    Args:
        squash_merge (PullRequest): A squash merged pull request

    Returns (list[UnSquashedCommit]): A list of UnSquashedCommit objects
    """
    return list(map(transform_to_unsquashed_commit, squash_merge.get_commits()))


if __name__ == "__main__":
    # fetch commit for
    # apache/zookeeper/commits/b6f0e5d5e0baf59038ac4381229437607746069a
    repo = get_repository("apache", "kafka")
    commit = repo.get_commit("c7c1364b0f0e5f5da30b85cc6173ea52fc6d0008")
    print(
        [
            file.diff_parsed
            for file in transform_to_unsquashed_commit(commit).modified_files
        ]
    )
