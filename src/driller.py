import csv
import json
import re
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


def get_defined_method(line: str) -> Optional[str]:
    pattern = (
        r"^\s*(public|private|protected)\s+(?:static\s+)?(?:final\s+)"
        + r"?[\w<>[\],\s]+\s+\w+\s*\([^)]*\)"
    )
    if bool(re.match(pattern, line)):
        match = re.match(pattern, line)
        if match is None:
            return None
        method_parts = line[match.span()[0] : match.span()[1]].split()
        for i, part in enumerate(method_parts):
            if "(" in part:
                if part.startswith("("):
                    method_name = method_parts[i - 1]
                    # function (internal) or function ( internal )
                else:
                    method_name = method_parts[i].split("(")[0]
                # function(internal) or function( internal )
        return method_name
    return None


def get_classes_used(diffs: dict[str, list[tuple[int, str]]]) -> set[str]:
    new_lines: list[tuple[int, str]] = diffs["added"]
    # Match patterns like: new ClassName() or ClassName.method()
    class_pattern = r"(?:new\s+(\w+)|(\w+)\.[\w<>]+\()"
    classes_referenced = set()
    for _, line in new_lines:
        matches = re.finditer(class_pattern, line)
        for match in matches:
            # Group 1 is from 'new ClassName()'
            # Group 2 is from 'ClassName.method()'
            class_name = match.group(1) or match.group(2)
            if class_name:
                classes_referenced.add(class_name)
    return classes_referenced


def get_new_methods(diffs: dict[str, list[tuple[int, str]]]) -> set[str]:
    added_content = diffs["added"]
    deleted_content = diffs["deleted"]
    plus_methods: set[str] = set()
    minus_methods: set[str] = set()
    for _, line in added_content:
        method_defined = get_defined_method(line)
        if method_defined is not None:
            plus_methods.add(method_defined)
    for _, line in deleted_content:
        method_defined = get_defined_method(line)
        if method_defined is not None:
            minus_methods.add(method_defined)
    return plus_methods - minus_methods


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
        assert file.new_path
        if file.new_path.endswith(".java"):
            added_methods = get_new_methods(file.diff_parsed)
            if len(added_methods) > 0:
                classes_referenced = get_classes_used(file.diff_parsed)
                return (
                    f"{file.new_path}{delimiter}"
                    + f"{added_methods}{delimiter}{classes_referenced}"
                )
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
