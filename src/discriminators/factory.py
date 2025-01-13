from typing import Literal, Type

from src.discriminators.before_same_after_discriminator import (
    BeforeSameAfterDiscriminator,
)
from src.discriminators.branch_discriminator import BranchDiscriminator
from src.discriminators.commit_seq_discriminator import CommitSequenceDiscriminator
from src.discriminators.discriminator import Discriminator
from src.discriminators.LLM_discriminator import LLMDiscriminator

DiscriminatorTypes = Literal["before_same_after", "commit_sequence", "llm", "branch"]


discriminator_factory: dict[DiscriminatorTypes, Type[Discriminator]] = {
    "before_same_after": BeforeSameAfterDiscriminator,
    "commit_sequence": CommitSequenceDiscriminator,
    "llm": LLMDiscriminator,
    "branch": BranchDiscriminator,
}
