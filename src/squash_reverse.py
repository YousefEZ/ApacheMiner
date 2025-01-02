from __future__ import annotations

import os
from functools import wraps
from typing import Any, Callable, ParamSpec, TypeVar

import rich.progress
from dotenv import load_dotenv
from github import Auth, Github
from github.PullRequest import PullRequest
from github.Repository import Repository

__all__ = ("get_squash_merges",)

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")

T = TypeVar("T")
P = ParamSpec("P")


def singleton(function: Callable[P, T]) -> Callable[P, T]:
    """A decorator that makes a function a singleton

    Args:
        function (Callable[[], T]): A function that returns an object

    Returns (Callable[[], T]): A singleton function
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


def get_squash_merges(org: str, name: str) -> frozenset[PullRequest]:
    """Gets all squash merges from a repository, by fetching all closed pull requests
    and filtering out merged pull requests that have a different merge commit sha than the head sha.

    Args:
        org (str): The organization name
        name (str): The repository name

    Returns (frozenset[PullRequest]): A set of pull requests that were squash merged
    """
    repository = get_repository(org, name)
    pull_requests = repository.get_pulls(state="closed", base=repository.default_branch)

    return frozenset(
        pull
        for pull in rich.progress.track(
            pull_requests,
            total=pull_requests.totalCount,
            description="Fetching Squash Merges",
        )
        if pull.merged_at is not None and pull.merge_commit_sha != pull.head.sha
    )
