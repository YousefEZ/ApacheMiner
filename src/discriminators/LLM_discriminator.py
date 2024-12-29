import os
import time
from dataclasses import dataclass
from functools import cached_property

import openai
import rich.progress

from .binding.file_types import FileName, SourceFile
from .binding.strategy import BindingStrategy
from .discriminator import Discriminator, Statistics
from .transaction import Commit, FileNumber, TransactionLog

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

    def query_tfd(
        self, source_id: FileNumber, commit_list: list[tuple[int, set[FileNumber]]]
    ) -> bool:
        prompt = (
            "Analyze these commits to determine if the source file follows test-first development. "
            + "The source file id is {source_id}, all other file ids are for its testers. "
            + f"Only output True or False. \n\n{[f"Commit #{idx}: Files: {files}\n" for (idx, files) in commit_list]}"
        )
        delay = (len(prompt) / TPM) * 60
        try:
            client = openai.OpenAI(api_key=os.environ["OPEN_AI_KEY"])
            completion = client.chat.completions.create(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
            )
            message = completion.choices[0].message.content.lower()
            if message == "true":
                return True
            elif message == "false":
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
            commit_list: list[Commit] = []
            source_path = FileName(
                os.path.join(os.path.basename(source_file.project), source_file.path)
            )
            source_id = self.transaction.mapping.name_to_id[source_path]
            file_collection = [source_id]
            for test_file in graph.source_to_test_links[source_file]:
                test_path = FileName(
                    os.path.join(os.path.basename(test_file.project), test_file.path)
                )
                file_collection.append(self.transaction.mapping.name_to_id[test_path])
            for commit in self.transaction.transactions.commits:
                commit_data: set[FileNumber] = set()
                for file_number in file_collection:
                    if file_number in commit.files:
                        commit_data.add(file_number)
                if len(commit_data) > 0:
                    commit_list.append((commit.number, commit_data))

            # check if the source file is tested first
            is_tfd = self.query_tfd(source_id, commit_list)
            output.append(Stats(source=source_file, is_tfd=is_tfd))

        return TestedFirstStatistics(test_statistics=output)
