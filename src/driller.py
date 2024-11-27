import csv
import json
from typing import Optional

import pydriller
import rich
import rich.progress
from bs4 import BeautifulSoup
from urllib3 import request


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


def drill_repository(
    url: str, output_file: str, progress: rich.progress.Progress
) -> None:
    commit_count = fetch_number_of_commits(url)
    with open(output_file, "w") as f:
        task = progress.add_task(
            f"Fetching commits for [cyan]{url}[/cyan]", total=commit_count
        )
        writer = csv.writer(f)
        for commit in pydriller.Repository(url).traverse_commits():
            progress.advance(task)
            writer.writerow(
                [
                    commit.hash,
                    "|".join(file.filename for file in commit.modified_files),
                ]
            )

        progress.tasks[task].visible = False
        # progress.refresh()
