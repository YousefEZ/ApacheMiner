from typing import NewType, TypedDict


class FileChanges(TypedDict):
    hash: str
    modification_type: str
    file: str
    parents: str


FileNumber = NewType("FileNumber", int)
