from typing import Literal, Type

from src.discriminators.binding.strategy import BindingStrategy
from src.discriminators.binding.import_strategy import (
    ImportStrategy,
    RecursiveImportStrategy,
)
from src.discriminators.binding.name_strategy import NameStrategy

Strategies = Literal["import", "name", "recursive_import"]


strategies: dict[Strategies, Type[BindingStrategy]] = {
    "import": ImportStrategy,
    "name": NameStrategy,
    "recursive_import": RecursiveImportStrategy,
}
