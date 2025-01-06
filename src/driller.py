import csv
import json
from typing import Generator, NamedTuple, Optional, Sequence

import pydriller
import rich
import rich.progress
from bs4 import BeautifulSoup
from git import Repo
from urllib3 import request

from src.custom_types.commit import CommitProtocol, ModifiedFileProtocol
from src.discriminators.transaction import modification_map
from src.squash_reverse import expand_squash_merge, get_squash_merges


class RemoteRepositoryInformation(NamedTuple):
    org: str
    name: str


def fetch_number_of_commits(url: str) -> Optional[int]:
    response = request(method="GET", url=url)
    if response.status != 200:
        return 0
    soup = BeautifulSoup(response.data, "html.parser")

    scripts = soup.find_all(
        "script",
        {"data-target": "react-partial.embeddedData", "type": "application/json"},
    )

    if not scripts:
        return None

    for script in scripts:
        if "commit" not in script.text:
            continue
        data = json.loads(script.text)
        return int(
            data["props"]["initialPayload"]["overview"]["commitCount"].replace(",", "")
        )

    return None


def get_commit_count(path: str) -> int:
    if pydriller.Repository._is_remote(path):
        commits = fetch_number_of_commits(path)
        assert commits is not None, "Failed to fetch commit count"
        return commits

    repo = Repo(path)
    branch = repo.active_branch
    return sum(1 for _ in repo.iter_commits(branch))


def format_file(file: ModifiedFileProtocol, delimiter: str = "|") -> str:
    if file.change_type == pydriller.ModificationType.RENAME:
        return f"{file.old_path}{delimiter}{file.new_path}"
    elif file.change_type == pydriller.ModificationType.DELETE:
        assert file.old_path is not None, "Old path should be set for deletion"
        return file.old_path
    elif (
        file.change_type == pydriller.ModificationType.ADD
        or file.change_type == pydriller.ModificationType.COPY
        or file.change_type == pydriller.ModificationType.MODIFY
        or file.change_type == pydriller.ModificationType.UNKNOWN
    ):
        assert file.new_path
        return file.new_path
    assert False, f"Unknown change type: {file.change_type}"


def get_repo_information(path: str) -> RemoteRepositoryInformation:
    chunks = Repo(path).remotes.origin.url.split(".git")[0].split("/")
    return RemoteRepositoryInformation(org=chunks[-2], name=chunks[-1])


def stiched_commits(
    path: str, progress: rich.progress.Progress, reverse_squash_merge: bool
) -> Generator[CommitProtocol, None, None]:
    """Expands squash merges into their individual commits and yields them

    Args:
        repository (pydriller.Repository): The repository to traverse

    Returns (Generator[pydriller.Commit, None, None]): The commits in the repository
    """
    hash_to_commits: dict[str, Sequence[CommitProtocol]] = {}

    if reverse_squash_merge:
        squashes = get_squash_merges(*get_repo_information(path), progress=progress)

        progress.console.print(
            f":mag_right: Found [cyan]{len(squashes)}[/cyan] squash merges to reverse",
            emoji=True,
        )
        # preprocess to avoid undefined behaviour when doing it within the for loop
        hash_to_commits = {
            squash.merge_commit_sha: expand_squash_merge(squash)
            for squash in progress.track(
                squashes, description="Expanding Squash Merges..."
            )
        }

    for commit in pydriller.Repository(path).traverse_commits():
        if commit.hash in hash_to_commits:
            yield from hash_to_commits[commit.hash]
        yield commit


def drill_repository(
    path: str,
    output_file: str,
    progress: rich.progress.Progress,
    reverse_squash_merge: bool,
    delimiter: str = "|",
) -> None:
    commit_count = get_commit_count(path)
    with open(output_file, "w") as f:
        task = progress.add_task(
            f"Fetching commits for [cyan]{path}[/cyan]", total=commit_count
        )
        writer = csv.DictWriter(
            f, fieldnames=["hash", "parents", "file", "modification_type"]
        )
        writer.writeheader()
        for commit in stiched_commits(path, progress, reverse_squash_merge):
            progress.advance(task)

            if not commit.modified_files:
                writer.writerow(
                    {
                        "hash": commit.hash,
                        "parents": delimiter.join(commit.parents),
                        "file": "",
                        "modification_type": "",
                    }
                )

            for file in commit.modified_files:
                writer.writerow(
                    {
                        "hash": commit.hash,
                        "parents": delimiter.join(commit.parents),
                        "file": format_file(file, delimiter),
                        "modification_type": modification_map[file.change_type],
                    }
                )

        progress.tasks[task].visible = False
