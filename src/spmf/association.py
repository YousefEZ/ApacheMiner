import os

from src.spmf import check_spmf


@check_spmf
def run_apriori(input_file: str, output_file: str, percentage: float) -> None:
    process = os.system(
        f"java -jar .spmf/spmf.jar run Apriori {input_file} {output_file} {percentage}%"
    )
    if process != 0:
        raise Exception("Apriori failed")
    ...
