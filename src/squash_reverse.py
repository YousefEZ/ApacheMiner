from __future__ import annotations

from typing import Any

from dotenv import load_dotenv
import os
from functools import lru_cache
from github import Github, Auth
from github.GithubObject import (
    CompletableGithubObject,
    NotSet,
    Opt,
    is_defined,
)
from github.PaginatedList import PaginatedList
from github.Repository import Repository

import rich.progress

__all__ = ("get_merge_commits",)

load_dotenv()

TOKEN = os.getenv("GITHUB_TOKEN")


@lru_cache
def get_github() -> Github:
    assert TOKEN is not None
    return Github(
        auth=Auth.Token(TOKEN),
        per_page=100,
        pool_size=15,
        retry=None,
        seconds_between_requests=0,
        seconds_between_writes=0,
    )


class CustomPullRequest(CompletableGithubObject):
    attributes: dict[str, Any]

    @property
    def merged(self) -> bool:
        return "merged_at" in self.attributes and self.attributes["merged_at"]

    @property
    def merge_commit_sha(self) -> str:
        return self.attributes["merge_commit_sha"]

    def _initAttributes(self) -> None:
        pass

    def _useAttributes(self, attributes: Any) -> None:
        self.attributes = attributes

    def _completeIfNeeded(self) -> None:
        pass


@lru_cache
def get_repository(org: str, name: str) -> Repository:
    return get_github().get_repo(f"{org}/{name}")


def get_custom_pulls(
    repository: Repository,
    state: Opt[str] = NotSet,
    sort: Opt[str] = NotSet,
    direction: Opt[str] = NotSet,
    base: Opt[str] = NotSet,
    head: Opt[str] = NotSet,
) -> PaginatedList[CustomPullRequest]:
    """Modified variant of get_pull_requests to avoid the need to construct the full object.
    It only fetches the merge_commit_sha attribute, and thus speeding up the process 45x.
    calls `GET /repos/{owner}/{repo}/pulls <https://docs.github.com/en/rest/reference/pulls>`

    Args:
        repository (Repository): The repository to fetch pull requests from

    Kwargs:
        state (str): Indicates the state of the pull requests to return.
                     Can be either open, closed, or all. Default: open
        sort (str): What to sort results by. Can be either created,
                    updated, popularity, or long-running. Default: created
        direction (str): The direction in which to sort pull requests. Can be either asc
                         or desc. Default: desc when sort is created or updated, otherwise
                         desc
        base (str): Filter pulls by base branch name. Example: gh-pages
        head (str): Filter pulls by head branch name. Example: new-topic

    Returns (PaginatedList[CustomPullRequest]): A list of pull requests
    """
    items = {
        "state": state,
        "sort": sort,
        "direction": direction,
        "base": base,
        "head": head,
    }

    return PaginatedList(
        CustomPullRequest,
        repository.requester,
        f"{repository.url}/pulls",
        {key: value for key, value in items.items() if is_defined(value)},
    )


def get_merge_commits(org: str, name: str) -> frozenset[str]:
    repository = get_repository(org, name)
    pull_requests = get_custom_pulls(
        repository, state="closed", base=repository.default_branch
    )

    return frozenset(
        pull.merge_commit_sha
        for pull in rich.progress.track(pull_requests, total=pull_requests.totalCount)
        if pull.merged
    )


if __name__ == "__main__":
    merge_commits = get_merge_commits("apache", "kafka")
    print("795390a3c856c98eb4934ddc996f35693bed8ac5" in merge_commits)
    print(len(merge_commits))
