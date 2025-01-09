from typing import NewType, TypedDict


class FileChanges(TypedDict):
    hash: str
    modification_type: str
    file: str
    parents: str
    new_methods: str
    classes_used: str


FileNumber = NewType("FileNumber", int)
