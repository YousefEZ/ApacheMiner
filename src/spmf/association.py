import json
from typing import Generator, NamedTuple, Optional

from src.spmf import check_spmf, run_spmf


ALGORITHM = "Apriori"


@check_spmf
def apriori(input_file: str, output_file: str, percentage: float) -> None:
    run_spmf(ALGORITHM, input_file, output_file, str(percentage))


class AprioriResults(NamedTuple):
    associated_files: list[list[str]]
    largest_associated: int


def get_associated_files(
    file: str, map_file: str, limit: int, must_have: Optional[str]
) -> Generator[list[str], None, None]:
    with open(map_file, "r") as map_reader:
        name_map = json.load(map_reader)

    with open(file, "r") as reader:
        for line in reader.readlines():
            raw_associated, _ = line.strip().split("#SUP:")
            associated = [
                name_map[name][-1] for name in raw_associated.strip().split(" ")
            ]
            assert None not in associated

            if 2 > len(associated) or len(associated) > limit:
                continue

            if must_have is None or any(
                must_have in name.lower() for name in associated
            ):
                yield associated


def analyze_apriori(
    output_file: str, map_file: str, limit: int, must_have: Optional[str]
) -> AprioriResults:
    associated_files = list(
        get_associated_files(output_file, map_file, limit, must_have)
    )
    largest_associated = max(len(associated) for associated in associated_files)

    return AprioriResults(
        associated_files=associated_files, largest_associated=largest_associated
    )
