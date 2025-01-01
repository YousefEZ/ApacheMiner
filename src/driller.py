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
from src.MergeFinder import MergeFinder

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
        or file.change_type == pydriller.ModificationType.MODIFY
    ):
        assert file.new_path
        return file.new_path

    assert False, f"Unknown change type: {file.change_type}"


def get_commit_count(path: str) -> int:
    if pydriller.Repository._is_remote(path):
        commits = fetch_number_of_commits(path)
        assert commits is not None, "Failed to fetch commit count"
        return commits

    repo = Repo(path)
    branch = repo.active_branch
    return sum(1 for _ in repo.iter_commits(branch))

def fix_entries(file_path: str, dict_fixes: dict):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    with open(file_path, 'w') as file:
        for line in lines:
            if line.strip() in dict_fixes.keys():
                file.write(dict_fixes[line.strip()] + '\n')
            else:
                file.write(line)


def find_last_n_commits(n: int, output_file: str,history: list):
    with open(output_file, "r") as r:
        lines = [line.strip() for line in r if line.strip()]
    last_commits = []
    for i in range(1,len(lines)):
        c = lines[-i].split(",")[0]
        if not c in last_commits and not commit_list:
            last_commits.append(c)
        if len(last_commits)>=n:
            break
    return last_commits


def drill_repository(
    path: str, output_file: str, progress: rich.progress.Progress, delimiter: str = "|"
) -> None:
    commit_count = get_commit_count(path)
    merge_list = MergeFinder(path).safe_get_merge_commits()
    with open(output_file, "w") as f:
        task = progress.add_task(
            f"Fetching commits for [cyan]{path}[/cyan]", total=commit_count
        )
        writer = csv.DictWriter(f, fieldnames=["hash", "file", "modification_type"])
        writer.writeheader()
        for commit in pydriller.Repository(path).traverse_commits():
            progress.advance(task)
            if commit.hash in merge_list and len(commit.parents) <2:
                # Squashed merged
                f.flush()
                last_commits = find_last_n_commits(commit.files,output_file,merge_list)
                
                pass
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
