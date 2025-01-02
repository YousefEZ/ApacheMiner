from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Literal, Optional, ParamSpec, Sequence, TypeVar, cast

import pydriller
import rich.progress
from dotenv import load_dotenv
from github import Auth, Github
from github.Commit import Commit
from github.PullRequest import PullRequest
from github.Repository import Repository
from pydriller import ModificationType

from src.types.commit import CommitProtocol, ModifiedFileProtocol

__all__ = ("get_squash_merges", "expand_squash_merge")

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

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
    _filename: str
    _change_type: pydriller.ModificationType
    _old_path: Optional[str] = field(default=None)
    _new_path: Optional[str] = field(default=None)

    @property
    def change_type(self) -> pydriller.ModificationType:
        return self._change_type

    @property
    def old_path(self) -> Optional[str]:
        return self._old_path

    @property
    def new_path(self) -> Optional[str]:
        return self._new_path


@dataclass(frozen=True)
class UnSquashedCommit(CommitProtocol):
    _modified_files: list[ChangedFile]
    _hash: str

    @property
    def modified_files(self) -> Sequence[ModifiedFileProtocol]:
        return self._modified_files

    @property
    def hash(self) -> str:
        return self._hash


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
    assert TOKEN is not None
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


def transform_to_unsquashed_commit(commit: Commit) -> UnSquashedCommit:
    """Analyzes the commit, by extracting the required infromation to
    generate a UnSquashedCommit object that abides by the CommitProtocol

    Args:
        commit (Commit): A commit object from PyGitHub

    Returns (UnSquashedCommit): A UnSquashedCommit object
    """
    return UnSquashedCommit(
        _modified_files=[
            ChangedFile(
                file.filename,
                change_type_mapping[cast(GitModificationType, file.status)],
                file.previous_filename,
                file.filename,
            )
            for file in commit.files
        ],
        _hash=commit.sha,
    )


def expand_squash_merge(squash_merge: PullRequest) -> list[UnSquashedCommit]:
    """Expands a squash merge by extracting all the commits that were squashed

    Args:
        squash_merge (PullRequest): A squash merged pull request

    Returns (list[UnSquashedCommit]): A list of UnSquashedCommit objects
    """
    return list(map(transform_to_unsquashed_commit, squash_merge.get_commits()))
