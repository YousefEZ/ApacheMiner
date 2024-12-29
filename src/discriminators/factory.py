from typing import Literal, Type

from src.discriminators.before_after_discriminator import BeforeAfterDiscriminator
from src.discriminators.commit_seq_discriminator import CommitSequenceDiscriminator
from src.discriminators.discriminator import Discriminator
from src.discriminators.LLM_discriminator import LLMDiscriminator

DiscriminatorTypes = Literal["before_after", "commit_sequence", "llm"]


discriminator_factory: dict[DiscriminatorTypes, Type[Discriminator]] = {
    "before_after": BeforeAfterDiscriminator,
    "commit_sequence": CommitSequenceDiscriminator,
    "llm": LLMDiscriminator,
}
