import csv
import json
from typing import Optional

import pydriller
import rich
import rich.progress
from bs4 import BeautifulSoup
from urllib3 import request

modification_map: dict[pydriller.ModificationType, str] = {
    pydriller.ModificationType.ADD: "A",
    pydriller.ModificationType.COPY: "C",
    pydriller.ModificationType.DELETE: "D",
    pydriller.ModificationType.MODIFY: "M",
    pydriller.ModificationType.RENAME: "R",
}


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
    url: str, output_file: str, progress: rich.progress.Progress, delimiter: str = "|"
) -> None:
    commit_count = fetch_number_of_commits(url)
    with open(output_file, "w") as f:
        task = progress.add_task(
            f"Fetching commits for [cyan]{url}[/cyan]", total=commit_count
        )
        writer = csv.DictWriter(f, fieldnames=["hash", "file", "modification_type"])
        for commit in pydriller.Repository(url).traverse_commits():
            progress.advance(task)
            for file in commit.modified_files:
                if file.change_type == pydriller.ModificationType.RENAME:
                    writer.writerow(
                        {
                            "hash": commit.hash,
                            "file": f"{file.old_path}{delimiter}{file.new_path}",
                            "modification_type": modification_map[
                                pydriller.ModificationType.RENAME
                            ],
                        }
                    )
                else:
                    writer.writerow(
                        {
                            "hash": commit.hash,
                            "file": file.filename,
                            "modification_type": modification_map[file.change_type],
                        }
                    )

        progress.tasks[task].visible = False
