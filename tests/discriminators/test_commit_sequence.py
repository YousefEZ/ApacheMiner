from collections import defaultdict

from pydriller import ModificationType as modification_type

from src.discriminators.binding.file_types import FileName, SourceFile, TestFile
from src.discriminators.binding.graph import Graph
from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.commit_seq_discriminator import CommitSequenceDiscriminator
from src.discriminators.transaction import (
    Commit,
    FileNumber,
    TransactionLog,
    TransactionMap,
    Transactions,
)


class MockTransactions(Transactions):
    pass


class MockTransactionMap(TransactionMap):
    @property
    def name_to_id(self) -> dict[FileName, FileNumber]:
        return {
            FileName(name): FileNumber(k)
            for k, v in self.id_to_names.items()
            for name in v
        }


class MockTransactionLog(TransactionLog):
    transactions: MockTransactions
    mapping: MockTransactionMap

    @classmethod
    def generate(cls, commit_list):
        transactions = MockTransactions(commits=[])
        mapping = MockTransactionMap(id_to_names={})
        file_id = 0
        for i, commit_info in enumerate(commit_list):
            commit = Commit(number=i, files={})
            transactions.commits.append(commit)
            for file, modification in commit_info:
                if isinstance(modification, tuple):
                    print(file.name, modification)
                    if modification[0] == modification_type.ADD:
                        print(file.name, modification)
                        mapping.id_to_names[FileNumber(file_id)] = [file.name]
                        file_id += 1
                    print(mapping.id_to_names, file.name, mapping.name_to_id, "\n")
                    commit.files[mapping.name_to_id[file.name]] = (
                        modification[0],
                        modification[1],
                        modification[2],
                    )
                else:
                    print(modification)
                    if modification == modification_type.ADD:
                        mapping.id_to_names[FileNumber(file_id)] = [file.name]
                        commit.files[FileNumber(file_id)] = modification_type.ADD
                        file_id += 1
                    else:
                        print(mapping.id_to_names)
                        commit.files[mapping.name_to_id[file.name]] = modification
        return cls(mapping=mapping, transactions=transactions)


class MockBindingStrategy(BindingStrategy):
    source_files: set[SourceFile]
    test_files: set[TestFile]
    test_to_source_links: dict[TestFile, set[SourceFile]]

    @classmethod
    def generate(self, files):
        source_files = set()
        test_files = set()
        test_to_source_links = defaultdict(set)
        # default basic implementation (alike name_strategy)
        for file in files:
            core_name = file.name.strip(".java")
            if core_name.endswith("-source"):
                source_files.add(file)
            if core_name.endswith("-test"):
                test_files.add(file)
                sources = list(core_name.strip("-test"))
                for source in sources:
                    source_file = SourceFile("", FileName(source + "-source.java"))
                    if source_file in files:
                        test_to_source_links[file].add(source_file)
                    else:
                        raise ValueError(
                            "Misconfigured test file. "
                            + f"{file} has no sourcefile {source_file}"
                        )
        self.source_files = source_files
        self.test_files = test_files
        self.test_to_source_links = test_to_source_links

    @classmethod
    def graph(self) -> Graph:
        return Graph(
            source_files=self.source_files,
            test_files=self.test_files,
            test_to_source_links=self.test_to_source_links,
        )


def generate(files, commit_list):
    transactions = MockTransactionLog.generate(commit_list)
    binding_strategy = MockBindingStrategy(None)
    binding_strategy.generate(files)

    return transactions, binding_strategy


sourceA = SourceFile("", "A-source.java")
sourceB = SourceFile("", "B-source.java")
testAB = TestFile("", "AB-test.java")
testA = TestFile("", "A-test.java")
testB = TestFile("", "B-test.java")


def test_mock_data():
    files = {sourceA, sourceB, testAB, testA, testB}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (sourceB, modification_type.ADD),
        },
        {
            (testAB, modification_type.ADD),
            (testA, modification_type.ADD),
            (sourceB, modification_type.MODIFY),
        },
        {(testB, modification_type.ADD)},
    ]
    transactions, binding_strategy = generate(files, commit_list)
    assert len(transactions.transactions.commits) == 3

    assert len(transactions.mapping.id_to_names) == 5
    assert (
        transactions.mapping.id_to_names[FileNumber(0)] == [sourceA.name]
        or transactions.mapping.id_to_names[FileNumber(0)] == [sourceB.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(1)] == [sourceA.name]
        or transactions.mapping.id_to_names[FileNumber(1)] == [sourceB.name]
    ), "first commit is identified with 0-1"
    assert (
        transactions.mapping.id_to_names[FileNumber(2)] == [testAB.name]
        or transactions.mapping.id_to_names[FileNumber(2)] == [testA.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(3)] == [testAB.name]
        or transactions.mapping.id_to_names[FileNumber(3)] == [testA.name]
    ), "second commit is identified with 2-4"
    assert transactions.mapping.id_to_names[FileNumber(4)] == [testB.name]
    assert len(binding_strategy.source_files) == 2
    assert binding_strategy.source_files == {sourceA, sourceB}
    assert len(binding_strategy.test_files) == 3
    assert binding_strategy.test_files == {testAB, testA, testB}

    graph = binding_strategy.graph()
    assert graph.test_to_source_links[testAB] == {
        sourceA,
        sourceB,
    }
    assert graph.test_to_source_links[testA] == {sourceA}
    assert graph.test_to_source_links[testB] == {sourceB}
    assert graph.source_to_test_links[sourceA] == {
        testAB,
        testA,
    }
    assert graph.source_to_test_links[sourceB] == {
        testAB,
        testB,
    }


def test_output_format():
    files = {}
    commit_list = []
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 0\nTest Elsewhere: 0"
    )


def test_found_tfd_split_commits():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
        },
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 1\nTest Elsewhere: 0"
    )

    # test case with multiple commits
    commit_list.append(
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"A-source"}),
                ),
            ),
        }
    )
    commit_list.append(
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    )
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 1\nTest Elsewhere: 0"
    )


def test_found_tfd_same_commits():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 1\nTest Elsewhere: 0"
    )

    # test case with multiple commits
    commit_list.append(
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"A-source"}),
                ),
            ),
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    )
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 1\nTest Elsewhere: 0"
    )


def test_failed_tfd():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
        {
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 0\nTest Elsewhere: 1"
    )

    # source commited without test
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 0\nTest Elsewhere: 1"
    )

    # source commited before test
    commit_list.append(
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"A-source"}),
                ),
            ),
        },
    )
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output() == "Test First Updates: 0\nTest Elsewhere: 1"
    )


def test_only_one_testfile_change_needed():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
            (
                testAB,
                (
                    modification_type.ADD,
                    frozenset({"method"}),
                    frozenset({"A-source", "B-source"}),
                ),
            ),
            (sourceB, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"A-source"}),
                ),
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {testA: [1]}


def test_other_modification_types_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
            (
                testAB,
                (
                    modification_type.ADD,
                    frozenset({"method"}),
                    frozenset({"A-source", "B-source"}),
                ),
            ),
            (sourceB, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
    ]
    different_modification_type = [
        {
            (
                testA,
                modification_type.COPY,
            ),
            (
                testAB,
                modification_type.RENAME,
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(
        files, commit_list + different_modification_type
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert not stats_sourceA.is_tfd
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {}


def test_non_feature_additive_changes_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
            (
                testAB,
                (
                    modification_type.ADD,
                    frozenset({"method"}),
                    frozenset({"A-source", "B-source"}),
                ),
            ),
            (sourceB, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
    ]
    modify_without_new_features = [
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset(),
                    frozenset(),
                ),
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(
        files, commit_list + modify_without_new_features
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert not stats_sourceA.is_tfd
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {}


def test_test_other_source_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
            (
                testAB,
                (
                    modification_type.ADD,
                    frozenset({"method"}),
                    frozenset({"A-source", "B-source"}),
                ),
            ),
            (sourceB, (modification_type.ADD, frozenset({"method"}), frozenset())),
        },
    ]
    new_feature_for_other_file = [
        {
            (
                testAB,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"B-source"}),
                ),
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    transactions, binding_strategy = generate(
        files, commit_list + new_feature_for_other_file
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert not stats_sourceA.is_tfd
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {}


def test_end_when_file_deleted():
    files = {sourceA, testA}
    commit_list = [
        {
            (sourceA, (modification_type.ADD, frozenset({"method"}), frozenset())),
            (
                testA,
                (modification_type.ADD, frozenset({"method"}), frozenset({"A-source"})),
            ),
        },
        {
            (
                testA,
                (
                    modification_type.MODIFY,
                    frozenset({"method"}),
                    frozenset({"A-source"}),
                ),
            ),
        },
        {
            (sourceA, modification_type.DELETE),
        },
    ]
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd
    assert len(stats_sourceA.changed_tests_per_commit) == 1
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0]}
