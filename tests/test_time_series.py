import random
import re
from collections import OrderedDict
from pathlib import Path

import hypothesis

from src.transaction import (
    TDDInfo,
    get_sequences,
    get_source_test_pairs,
    time_series_analysis,
)

input_file = Path.cwd() / "tests" / "data" / "commits.txt"
shuffle_file = Path.cwd() / "tests" / "data" / "shuffled_commits.txt"


def test_output_format():
    """Verify that series output is formatted correctly"""
    series, _ = time_series_analysis(input_file, 1, 3, False)
    pattern = re.compile(
        r"\(\d+,\d+\) #TFD: \d*\.?\d+ #TDD: \d*\.?\d+ "
        + r"#DIST: \d*\.?\d+ #CONF: \d*\.?\d+"
    )
    for line in series:
        assert isinstance(line, TDDInfo), "series output should be in TDDInfo"
        assert (
            pattern.match(str(line)) is not None
        ), "series output should be formatted correctly"


def test_intracommit_order_changes_nothing():
    """If the order of changes in a commit changes, the output should be the same"""
    series1, _ = time_series_analysis(input_file, 1, 3, False)
    # shuffle_hash_lines(self.input_file, self.shuffle_file)
    series2, _ = time_series_analysis(shuffle_file, 1, 3, False)
    # compare numerically, regardless of order or mapping
    set1 = {(dp.tfd, dp.tdd, tuple(dp.distances)) for dp in series1}
    set2 = {(dp.tfd, dp.tdd, tuple(dp.distances)) for dp in series2}
    assert set1 == set2, "series output should be the same regardless of commit order"


def shuffle_hash_lines(filename):
    # Ordered dictionary to maintain hash order
    hash_groups = OrderedDict()
    hash_order = []

    # Read and group lines by hash
    with open(filename, "r") as file:
        for line in file:
            line = line.strip()
            if line:  # Skip empty lines
                hash_value, *rest = line.split(",")
                if hash_value not in hash_groups:
                    hash_groups[hash_value] = []
                    hash_order.append(hash_value)
                hash_groups[hash_value].append(",".join(rest))

    # Shuffle contents within each hash group
    for hash_value in hash_groups:
        random.shuffle(hash_groups[hash_value])

    # Write back maintaining hash order
    with open("shuffled_output.txt", "w") as outfile:
        for hash_value in hash_order:
            for content in hash_groups[hash_value]:
                outfile.write(f"{hash_value},{content}\n")


# PROPERTY-BASED TESTING #
@hypothesis.given(
    hypothesis.strategies.integers(min_value=0, max_value=5),  # tfd_leniency
    hypothesis.strategies.integers(min_value=0, max_value=10),  # tdd_leniency
)
def test_time_series_properties(tfd_leniency, tdd_leniency):
    """Property-based test for time series analysis function"""
    series, map = time_series_analysis(input_file, tfd_leniency, tdd_leniency, False)
    sequence_lines, _, _ = get_sequences(input_file, False)
    pairs = get_source_test_pairs(map.names.items())

    for datapoint in series:
        assert 0 <= datapoint.tfd <= 1, "TFD should be a ratio between 0 and 1"
        assert 0 <= datapoint.tdd <= 1, "TDD should be a ratio between 0 and 1"

        mean, conf = datapoint.get_stats()
        assert 0 <= mean <= tdd_leniency, "Mean should be <= max TDD distance"
        assert 0 <= conf <= 1.0, "Confidence should be between 0 and 1"

        assert (
            datapoint.test == pairs[datapoint.source]
        ), "Source-test pairs should match"
        assert (
            datapoint.source == pairs[datapoint.test]
        ), "Source-test pairs should match"

        number_of_commits = (
            len(sequence_lines[datapoint.source].split(" -1 ")) - 1
        )  # remove final -2 and get number of (<commit> id -1)*
        assert (
            len(datapoint.distances) <= number_of_commits - 1
        ), "Number of TDD distances at most the total number of changes"
