from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property

from pydriller import ModificationType as modification_type

from src.discriminators.binding.file_types import (
    FileName,
    ProgramFile,
    SourceFile,
    TestFile,
)
from src.discriminators.binding.graph import Graph
from src.discriminators.binding.repository import Files, Repository
from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.commit_seq_discriminator import CommitSequenceDiscriminator
from src.discriminators.file_types import FileChanges
from src.discriminators.transaction import (
    FileNumber,
    TransactionBuilder,
    modification_map,
)


@dataclass(frozen=True)
class MockRepository(Repository):
    all_files: set[ProgramFile]

    @cached_property
    def files(self) -> Files:
        return Files(
            source_files={
                file for file in self.all_files if isinstance(file, SourceFile)
            },
            test_files={file for file in self.all_files if isinstance(file, TestFile)},
        )


@dataclass(frozen=True)
class MockBindingStrategy(BindingStrategy):
    repository: Repository

    def graph(self) -> Graph:
        source_file_mapping = {
            file.name: file for file in self.repository.files.source_files
        }
        test_to_source_links = defaultdict(set)

        for test in self.repository.files.test_files:
            for source in test.name.split("-")[0]:
                name = FileName(source + "-source.java")
                test_to_source_links[test].add(source_file_mapping[name])

        return Graph(
            source_files=self.repository.files.source_files,
            test_files=self.repository.files.test_files,
            test_to_source_links=test_to_source_links,
        )


def generate_file_changes(
    c_hash: int,
    changes: tuple[
        ProgramFile,
        modification_type | tuple[modification_type, set[str], set[str]],
    ],
) -> FileChanges:
    file, modification = changes
    if isinstance(modification, tuple):
        return FileChanges(
            hash=str(c_hash),
            modification_type=modification_map[modification[0]],
            file=file.name,
            new_methods="|".join(modification[1]),
            classes_used="|".join(modification[2]),
            parents=str(c_hash - 1) if c_hash > 0 else "",
        )
    return FileChanges(
        hash=str(c_hash),
        modification_type=modification_map[modification],
        file=file.name,
        parents=str(c_hash - 1) if c_hash > 0 else "",
        new_methods="",
        classes_used="",
    )


def convert_commit_list(
    c_list: list[
        set[
            tuple[
                ProgramFile,
                modification_type | tuple[modification_type, set[str], set[str]],
            ]
        ]
    ],
) -> list[FileChanges]:
    return [
        generate_file_changes(c_hash, change)
        for c_hash, changes in enumerate(c_list)
        for change in changes
    ]


def generate(
    files: set[ProgramFile],
    commit_list: list[
        set[
            tuple[
                ProgramFile,
                modification_type | tuple[modification_type, set[str], set[str]],
            ]
        ]
    ],
):
    repository = MockRepository(all_files=files)
    binding_strategy = MockBindingStrategy(repository)

    return convert_commit_list(commit_list), binding_strategy


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
    commit_data, binding_strategy = generate(files, commit_list)
    transactions = TransactionBuilder.build_from_groups(
        TransactionBuilder.group_file_changes(commit_data)
    )
    graph = binding_strategy.graph()

    assert len(transactions.transactions.commits) == 3

    assert len(transactions.mapping.id_to_names) == 5
    assert (
        transactions.mapping.id_to_names[FileNumber(1)] == [sourceA.name]
        or transactions.mapping.id_to_names[FileNumber(1)] == [sourceB.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(2)] == [sourceA.name]
        or transactions.mapping.id_to_names[FileNumber(2)] == [sourceB.name]
    ), "first commit is identified with 0-1"
    assert (
        transactions.mapping.id_to_names[FileNumber(3)] == [testAB.name]
        or transactions.mapping.id_to_names[FileNumber(3)] == [testA.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(4)] == [testAB.name]
        or transactions.mapping.id_to_names[FileNumber(4)] == [testA.name]
    ), "second commit is identified with 2-4"
    assert transactions.mapping.id_to_names[FileNumber(5)] == [testB.name]
    assert len(graph.source_files) == 2
    assert graph.source_files == {sourceA, sourceB}
    assert len(graph.test_files) == 3
    assert graph.test_files == {testAB, testA, testB}

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
    files = set()
    commit_list = []
    transactions, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert (
        discriminator.statistics.output()
        == "Threshold: 1.0\nTest First Updates: 0\nTest Elsewhere: 0\nThreshold: 0.75\nTest First Updates: 0\nTest Elsewhere: 0\nThreshold: 0.5\nTest First Updates: 0\nTest Elsewhere: 0\nUntested Files: 0"
    )


def test_found_tfd_split_commits():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (
                testA,
                modification_type.ADD,
            ),
        },
        {
            (sourceA, modification_type.ADD),
        },
    ]
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == {sourceA}
    assert stats.non_test_first(1.0) == set()
    assert stats.untested_source_files == set()

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
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics

    assert stats.test_first(1.0) == {sourceA}
    assert stats.non_test_first(1.0) == set()
    assert stats.untested_source_files == set()

    # assert (
    #    discriminator.statistics.output()
    #    == "Test First Updates: 1\nTest Elsewhere: 0\nUntested Files: 0\n"
    # )


def test_found_tfd_same_commits():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (
                testA,
                modification_type.ADD,
            ),
            (sourceA, modification_type.ADD),
        },
    ]
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == {sourceA}
    assert stats.non_test_first(1.0) == set()
    assert stats.untested_source_files == set()

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
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == {sourceA}
    assert stats.non_test_first(1.0) == set()
    assert stats.untested_source_files == set()


def test_failed_tfd():
    files = {sourceA, testA}
    # base case
    commit_list = [
        {
            (sourceA, modification_type.ADD),
        },
        {
            (
                testA,
                modification_type.ADD,
            ),
        },
    ]
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == set()
    assert stats.non_test_first(1.0) == {sourceA}
    assert stats.untested_source_files == set()

    # source commited without test
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == set()
    assert stats.non_test_first(1.0) == {sourceA}
    assert stats.untested_source_files == set()

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
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats = discriminator.statistics
    assert stats.test_first(1.0) == set()
    assert stats.non_test_first(1.0) == {sourceA}
    assert stats.untested_source_files == set()


def test_only_one_testfile_change_needed():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
            ),
            (
                testAB,
                modification_type.ADD,
            ),
            (sourceB, modification_type.ADD),
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
    commit_data, binding_strategy = generate(files, commit_list)
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd(1.0)
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {testA: [1]}


def test_other_modification_types_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
            ),
            (testAB, modification_type.ADD),
            (sourceB, modification_type.ADD),
        },
    ]
    different_modification_type = [
        {
            (
                testA,
                modification_type.UNKNOWN,
            ),
            (
                testAB,
                modification_type.MODIFY,
            ),
        },
        {
            (sourceA, (modification_type.MODIFY, frozenset({"method"}), frozenset())),
        },
    ]
    commit_data, binding_strategy = generate(
        files, commit_list + different_modification_type
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd(1.0)
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {testAB: [1]}


def test_non_feature_additive_changes_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
            ),
            (
                testAB,
                modification_type.ADD,
            ),
            (sourceB, modification_type.ADD),
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
    commit_data, binding_strategy = generate(
        files, commit_list + modify_without_new_features
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd(1.0)
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {testA: [1]}


def test_test_other_source_not_counted():
    files = {sourceA, testA, testAB, sourceB}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
            ),
            (
                testAB,
                modification_type.ADD,
            ),
            (sourceB, modification_type.ADD),
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
    commit_data, binding_strategy = generate(
        files, commit_list + new_feature_for_other_file
    )
    assert binding_strategy.graph().source_to_test_links[sourceA] == {testA, testAB}
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd(1.0)
    assert len(stats_sourceA.changed_tests_per_commit) == 2
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0], testAB: [0]}
    assert stats_sourceA.changed_tests_per_commit[1] == {testAB: [1]}


def test_end_when_file_deleted():
    files = {sourceA, testA}
    commit_list = [
        {
            (sourceA, modification_type.ADD),
            (
                testA,
                modification_type.ADD,
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
    commit_data, binding_strategy = generate(files, commit_list)
    discriminator = CommitSequenceDiscriminator(commit_data, binding_strategy)
    stats_sourceA = discriminator.statistics.test_statistics[0]
    for stats in discriminator.statistics.test_statistics:
        if stats.source == sourceA:
            stats_sourceA = stats
            break
    assert stats_sourceA.is_tfd(1.0)
    assert len(stats_sourceA.changed_tests_per_commit) == 1
    assert stats_sourceA.changed_tests_per_commit[0] == {testA: [0]}
