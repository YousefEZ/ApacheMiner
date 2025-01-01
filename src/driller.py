import csv
import json
from typing import Optional

import pydriller
import rich
import rich.progress
from bs4 import BeautifulSoup
from git import Repo
from urllib3 import request

from src.discriminators.transaction import modification_map


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


def format_file(file: pydriller.ModifiedFile, delimiter: str = "|") -> str:
    if file.change_type == pydriller.ModificationType.RENAME:
        return f"{file.old_path}{delimiter}{file.new_path}"
    elif file.change_type == pydriller.ModificationType.DELETE:
        assert file.old_path
        return file.old_path
    elif (
        file.change_type == pydriller.ModificationType.ADD
        or file.change_type == pydriller.ModificationType.COPY
    ):
        assert file.new_path
        return file.new_path
    elif file.change_type == pydriller.ModificationType.MODIFY:
        return (
            f"{file.new_path}{delimiter}"
            + f"{file.added_lines}{delimiter}{file.deleted_lines}"
        )

    assert False, f"Unknown change type: {file.change_type}"


def get_commit_count(path: str) -> int:
    if pydriller.Repository._is_remote(path):
        commits = fetch_number_of_commits(path)
        assert commits is not None, "Failed to fetch commit count"
        return commits

    repo = Repo(path)
    branch = repo.active_branch
    return sum(1 for _ in repo.iter_commits(branch))


def drill_repository(
    path: str, output_file: str, progress: rich.progress.Progress, delimiter: str = "|"
) -> None:
    commit_count = get_commit_count(path)
    with open(output_file, "w") as f:
        task = progress.add_task(
            f"Fetching commits for [cyan]{path}[/cyan]", total=commit_count
        )
        writer = csv.DictWriter(f, fieldnames=["hash", "file", "modification_type"])
        writer.writeheader()
        for commit in pydriller.Repository(path).traverse_commits():
            progress.advance(task)
            for file in commit.modified_files:
                if file.change_type == pydriller.ModificationType.UNKNOWN:
                    # this is persmission changes
                    continue

                writer.writerow(
                    {
                        "hash": commit.hash,
                        "file": format_file(file, delimiter),
                        "modification_type": modification_map[file.change_type],
                    }
                )

        progress.tasks[task].visible = False
