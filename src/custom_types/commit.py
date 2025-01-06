from typing import Optional, Protocol, Sequence

import pydriller


class ModifiedFileProtocol(Protocol):
    @property
    def change_type(self) -> pydriller.ModificationType: ...

    @property
    def old_path(self) -> Optional[str]: ...

    @property
    def new_path(self) -> Optional[str]: ...

    @property
    def diff_parsed(self) -> dict[str, list[tuple[int, str]]]: ...


class CommitProtocol(Protocol):
    @property
    def modified_files(
        self,
    ) -> Sequence[ModifiedFileProtocol]: ...

    @property
    def hash(self) -> str: ...

    @property
    def parents(self) -> list[str]: ...
