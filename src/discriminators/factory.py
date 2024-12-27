from typing import Literal, Type

from src.discriminators.discriminator import Discriminator
from src.discriminators.before_after_discriminator import BeforeAfterDiscriminator

DiscriminatorTypes = Literal["before_after"]


discriminator_factory: dict[DiscriminatorTypes, Type[Discriminator]] = {
    "before_after": BeforeAfterDiscriminator,
}
