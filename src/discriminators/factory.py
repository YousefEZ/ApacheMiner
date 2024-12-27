from typing import Literal, Type

from src.discriminators.before_after_discriminator import BeforeAfterDiscriminator
from src.discriminators.discriminator import Discriminator

DiscriminatorTypes = Literal["before_after"]


discriminator_factory: dict[DiscriminatorTypes, Type[Discriminator]] = {
    "before_after": BeforeAfterDiscriminator,
}
