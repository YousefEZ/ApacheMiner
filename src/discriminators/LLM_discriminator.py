import os
import time
from dataclasses import dataclass
from functools import cached_property

import openai
import rich.progress
from pydriller import ModificationType

from .binding.file_types import FileName, SourceFile
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .file_types import FileNumber
from .transaction import Commit, File, TransactionLog

console = rich.console.Console()
TPM = 100000


@dataclass(frozen=True)
class Stats:
    source: SourceFile
    is_tfd: bool


@dataclass(frozen=True)
class TestedFirstStatistics(Statistics):
    test_statistics: list[Stats]

    @cached_property
    def test_first(self) -> set[SourceFile]:
        return set(
            [statistic.source for statistic in self.test_statistics if statistic.is_tfd]
        )

    @cached_property
    def non_test_first(self) -> set[SourceFile]:
        return (
            set([statistic.source for statistic in self.test_statistics])
            - self.test_first
        )

    def output(self) -> str:
        return (
            f"Test First Updates: {len(self.test_first)}\n"
            + f"Test Elsewhere: {len(self.non_test_first)}"
        )


@dataclass(frozen=True)
class LLMDiscriminator(Discriminator):
    transaction: TransactionLog
    file_binder: BindingStrategy

    def adds_features(self, file_commit_info: File) -> bool:
        """Does this commit add new methods to the file?"""
        if file_commit_info.modification_type == ModificationType.ADD:
            return True  # auto-accept file creations
        if file_commit_info.modification_type != ModificationType.MODIFY:
            return False  # not a modification
        if len(file_commit_info.new_methods) == 0:
            return False  # not a modification with method additions
        return True

    def get_fc(self, commit: Commit, file_number: FileNumber) -> File:
        for fc in commit.files:
            if fc.file_number == file_number:
                return fc
        raise ValueError("File not found in commit")

    def query_tfd(
        self, source_id: FileNumber, commit_list: list[tuple[int, set[FileNumber]]]
    ) -> bool:
        prompt = (
            "Analyze these commits to determine if the source file follows "
            + "test-first development. "
            + f"The source file id is {source_id}, all other file ids are for its "
            + "testers. Only output True or False. \n\n"
            + f"{[f"Commit #{idx}: Files: {files}\n" for (idx, files) in commit_list]}"
        )
        delay = (len(prompt) / TPM) * 60
        try:
            client = openai.OpenAI(api_key=os.environ["OPEN_AI_KEY"])
            completion = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
            )
            message = completion.choices[0].message.content
            if message is None:
                raise ValueError("No response from OpenAI")
            if message.lower() == "true":
                return True
            elif message.lower() == "false":
                return False
            else:
                print(f">> Invalid response from OpenAI: {message}")
                return self.query_tfd(source_id, commit_list)
        except openai.RateLimitError:
            print(f">> Rate limit exceeded, waiting for {delay}s")
            time.sleep(delay + 1)
            return self.query_tfd(source_id, commit_list)

    @property
    def statistics(self) -> TestedFirstStatistics:
        graph = self.file_binder.graph()
        output = []
        for source_file in rich.progress.track(graph.source_files):
            if source_file not in graph.source_to_test_links:
                continue  # no tests for this source file

            # collect relevant commits
            commit_list: list[tuple[int, set[FileNumber]]] = []
            source_path = FileName(source_file.path)
            source_id = self.transaction.mapping.name_to_id[source_path]
            file_collection = [source_id]
            for test_file in graph.source_to_test_links[source_file]:
                test_path = FileName(test_file.path)
                file_collection.append(self.transaction.mapping.name_to_id[test_path])
            for commit in self.transaction.transactions.commits:
                commit_data: set[FileNumber] = set()
                for file_number in file_collection:
                    if file_number in commit.file_numbers:
                        file_commit = self.get_fc(commit, file_number)
                        if self.adds_features(file_commit):
                            commit_data.add(file_number)
                if len(commit_data) > 0:
                    commit_list.append((commit.number, commit_data))

            # check if the source file is tested first
            is_tfd = self.query_tfd(source_id, commit_list)
            output.append(Stats(source=source_file, is_tfd=is_tfd))

        return TestedFirstStatistics(test_statistics=output)
