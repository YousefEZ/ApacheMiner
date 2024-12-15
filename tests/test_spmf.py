import random
import re
from collections import OrderedDict
from pathlib import Path

from src.transaction import TDDInfo, get_sequences, get_source_test_pairs, my_spmf


class TestSPMF:
    input_file = Path.cwd() / "tests" / "data" / "commits.txt"
    shuffle_file = Path.cwd() / "tests" / "data" / "shuffled_commits.txt"

    def test_spmf_output_format(self):
        """Verify that SPMF output is formatted correctly"""
        spmf, _ = my_spmf(self.input_file, 1, 3, False)
        pattern = re.compile(
            r"\(\d+,\d+\) #TFD: \d*\.?\d+ #TDD: \d*\.?\d+ "
            + r"#DIST: \d*\.?\d+ #CONF: \d*\.?\d+"
        )
        for line in spmf:
            assert isinstance(line, TDDInfo), "SPMF output should be in TDDInfo"
            assert (
                pattern.match(str(line)) is not None
            ), "SPMF output should be formatted correctly"

    def test_spmf_output_stats(self):
        """Verify that SPMF output statistics are within expected ranges"""
        tfd_leniency, tdd_leniency = 1, 3
        spmf, _ = my_spmf(self.input_file, tfd_leniency, tdd_leniency, False)
        sequence_lines = get_sequences(self.input_file, False)[0]
        for datapoint in spmf:
            mean, stdev = datapoint.get_stats()
            assert 0 <= mean <= tdd_leniency, "Mean should be <= max TDD distance"
            assert 0 <= datapoint.tfd <= 1, "TFD should be a ratio between 0 and 1"
            assert 0 <= datapoint.tdd <= 1, "TDD should be a ratio between 0 and 1"
            number_of_commits = (
                len(sequence_lines[datapoint.source].split(" -1 ")) - 1
            )  # remove final -2 and get number of (<commit> id -1)*
            assert (
                len(datapoint.distances) <= number_of_commits - 1
            ), "Number of TDD distances at most the total number of changes"

    def test_spmf_lines_match_pairs(self):
        """Verify that SPMF output matches source-test pairs"""
        spmf, map = my_spmf(self.input_file, 1, 3, False)
        pairs = get_source_test_pairs(map.names.items())
        assert len(pairs) > 0, "Pairs should not be empty"
        for datapoint in spmf:
            assert (
                datapoint.source in pairs
            ), "Source file should be in source-test pairs"
            assert datapoint.test in pairs, "Test file should be in source-test pairs"
            assert (
                pairs[datapoint.source] == datapoint.test
            ), "Source-test pairs should match"
            assert (
                pairs[datapoint.test] == datapoint.source
            ), "Source-test pairs should be symmetric"

    def test_spmf_intracommit_order_changes_nothing(self):
        """If the order of changes in a commit changes, the output should be the same"""
        spmf1, _ = my_spmf(self.input_file, 1, 3, False)
        # shuffle_hash_lines(self.input_file, self.shuffle_file)
        spmf2, _ = my_spmf(self.shuffle_file, 1, 3, False)
        # compare numerically, regardless of order or mapping
        set1 = {(dp.tfd, dp.tdd, tuple(dp.distances)) for dp in spmf1}
        set2 = {(dp.tfd, dp.tdd, tuple(dp.distances)) for dp in spmf2}
        assert set1 == set2, "SPMF output should be the same regardless of commit order"


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
