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
    pass


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
            for file, modification, plus_minus in commit_info:
                commit.files[FileNumber(file_id)] = (modification, plus_minus)
                if modification == modification_type.ADD:
                    mapping.id_to_names[FileNumber(file_id)] = [file.name]
                    file_id += 1
        return cls(mapping=mapping, transactions=transactions)


class MockBindingStrategy(BindingStrategy):
    source_files: set[SourceFile]
    test_files: set[TestFile]
    test_to_source_links: dict[TestFile, set[SourceFile]]

    @classmethod
    def generate(self, files):
        source_files: set[SourceFile] = set()
        test_files: set[TestFile] = set()
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
                    source_name = FileName(source + "-source.java")
                    source_file = SourceFile(None, source_name)
                    if source_file in files:
                        test_to_source_links[file].add(source_file)
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


sourceA = SourceFile(FileName(""), FileName("A-source.java"))
sourceB = SourceFile(FileName(""), FileName("B-source.java"))
testAB = TestFile(FileName(""), FileName("AB-test.java"))
testA = TestFile(FileName(""), FileName("A-test.java"))
testB = TestFile(FileName(""), FileName("B-test.java"))


def test_mock_data():
    files = {sourceA, sourceB, testAB, testA, testB}
    commit_list = [
        {
            (sourceA, modification_type.ADD, ()),
            (sourceB, modification_type.ADD, ()),
        },
        {
            (testAB, modification_type.ADD, ()),
            (testA, modification_type.ADD, ()),
            (sourceB, modification_type.MODIFY, (1, 2)),
        },
        {(testB, modification_type.ADD, ())},
    ]
    transactions, binding_strategy = generate(files, commit_list)
    assert len(transactions.transactions.commits) == 3

    assert len(transactions.mapping.id_to_names) == 5
    assert (
        transactions.mapping.id_to_names[FileNumber(0)] == [sourceA.name]
        or [sourceB.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(1)] == [sourceA.name]
        or [sourceB.name]
    ), "first commit is identified with 0-1"
    assert (
        transactions.mapping.id_to_names[FileNumber(2)] == [testAB.name] or [testA.name]
    ) and (
        transactions.mapping.id_to_names[FileNumber(3)] == [testAB.name] or [testA.name]
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


def test_run():
    files = {sourceA, sourceB, testAB, testA, testB}
    commit_list = [
        {
            (sourceA, modification_type.ADD, ()),
            (sourceB, modification_type.ADD, ()),
        },
        {
            (testAB, modification_type.ADD, ()),
            (testA, modification_type.ADD, ()),
            (sourceB, modification_type.MODIFY, (1, 2)),
        },
        {(testB, modification_type.ADD, ())},
    ]
    transactions, binding_strategy = generate(files, commit_list)
    print(transactions.mapping.id_to_names)
    print(transactions.mapping.name_to_id)
    discriminator = CommitSequenceDiscriminator(transactions, binding_strategy)
    assert discriminator.statistics
