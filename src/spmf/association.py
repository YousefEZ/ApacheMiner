import json
from typing import NamedTuple, Optional

from src.spmf import check_spmf, run_spmf


ALGORITHM = "Apriori"


@check_spmf
def apriori(input_file: str, output_file: str, percentage: float) -> None:
    run_spmf(ALGORITHM, input_file, output_file, str(percentage))


class AprioriResults(NamedTuple):
    associated_files: list[list[str]]
    largest_associated: int


def analyze_apriori(
    output_file: str, map_file: str, limit: int, display: bool, must_have: Optional[str]
) -> AprioriResults:
    with open(map_file, "r") as map_reader:
        name_map = json.load(map_reader)

    associated_files: list[list[str]] = []
    largest_associated = 1
    with open(output_file, "r") as reader:
        while line := reader.readline():
            raw_associated, _ = line.strip().split("#SUP:")
            associated: list[str] = list(
                map(
                    lambda files: files[-1],
                    map(name_map.get, raw_associated.strip().split(" ")),
                )
            )
            assert None not in associated
            if (
                2 <= len(associated) <= limit
                and display
                and (
                    must_have is None
                    or any(
                        map(lambda name: must_have.lower() in name.lower(), associated)
                    )
                )
            ):
                associated_files.append(associated)
                largest_associated = max(largest_associated, len(associated))

    return AprioriResults(
        associated_files=associated_files, largest_associated=largest_associated
    )
