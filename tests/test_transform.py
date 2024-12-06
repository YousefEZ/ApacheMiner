from pathlib import Path

from src.transaction import (
    TransactionMap,
    convert_for_spm,
    convert_into_transaction,
    get_source_test_pairs,
)


class TestTransform:
    input_file = Path.cwd() / "tests" / "data" / "commits.txt"

    def test_both_transforms_use_same_map(self):
        """Verify that list and sequence transforms produce consistent map files"""
        # Run both transformations
        list_transactions = convert_into_transaction(self.input_file)
        list_map = list_transactions.maps
        _, spm_map = convert_for_spm(self.input_file)

        # Maps should contain same file mappings
        assert isinstance(list_map, TransactionMap) and isinstance(
            spm_map, TransactionMap
        ), "Maps should be of the TransactionMap type"
        assert len(list_map.ids) == len(spm_map.ids), "Map IDs should have same length"
        assert (
            list_map.ids == spm_map.ids
        ), "Maps should contain identical mappings in same order"
        assert len(list_map.names) == len(
            spm_map.names
        ), "Map IDs should have same length"
        assert (
            list_map.names == spm_map.names
        ), "Maps should contain identical mappings in same order"

    def test_map_format(self):
        """Verify that map files are formatted correctly"""
        transactions, map = convert_for_spm(self.input_file)
        assert len(map.names) > 0, "Map file should not be empty"
        assert isinstance(
            map, TransactionMap
        ), "Map should be of the TransactionMap type"
        for key, value in map.names.items():
            assert isinstance(key, int), "Map key should be numeric"
            assert isinstance(value, list), "Map value should be a list of strings"
            for item in value:
                assert isinstance(item, str), "Map value should be a list of strings"

    def test_spm_output_format(self):
        """Verify that SPM output is formatted correctly"""
        transactions, map = convert_for_spm(self.input_file)
        for line in transactions:
            assert isinstance(line, str), "Transactions should be in string format"
            assert line.endswith("-2"), "Transactions should end with -2"
            line_split = line.split(" -1 ")
            del line_split[-1]  # remove -2 element
            for item in line_split:
                parts = item.split(" ")
                assert len(parts) == 2, "Transaction item should have two parts"
                assert parts[0].startswith("<") and parts[0].endswith(
                    ">"
                ), "Transaction item should be wrapped in angle brackets"
                assert parts[1].isdigit(), "Transaction item should be numeric"

    def test_spm_lines_match_pairs(self):
        """Verify that SPM transactions contain correct source-test file pairs"""
        transactions, map = convert_for_spm(self.input_file)
        pairs = get_source_test_pairs(map.names.items())
        for line in transactions:
            for source_idx in pairs:
                print(
                    source_idx,
                    map.names[source_idx],
                    pairs[source_idx],
                    map.names[int(pairs[source_idx])],
                )
                if f" {source_idx} " in line:
                    assert (
                        f" {pairs[source_idx]} " in line
                    ), "Source files should contain matching test file"
                if f" {pairs[source_idx]} " in line:
                    assert (
                        f" {source_idx} " in line
                    ), "Test files should contain matching source file"
