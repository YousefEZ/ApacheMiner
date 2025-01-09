from functools import lru_cache
import re
from typing import Optional

from src.discriminators.binding.file_types import ProgramFile
from src.discriminators.binding.repositories.languages.language import Language


class JavaLanguage(Language):
    SUFFIX: str = ".java"

    @staticmethod
    def get_defined_method(line: str) -> Optional[str]:
        pattern = (
            r"^\s*(public|private|protected)\s+(?:static\s+)?(?:final\s+)"
            + r"?[\w<>[\],\s]+\s+\w+\s*\([^)]*\)"
        )
        if bool(re.match(pattern, line)):
            match = re.match(pattern, line)
            if match is None:
                return None
            method_parts = line[match.span()[0] : match.span()[1]].split()
            method_name: Optional[str] = None
            for i, part in enumerate(method_parts):
                if "(" in part:
                    if part.startswith("("):
                        method_name = method_parts[i - 1]
                        # function (internal) or function ( internal )
                    else:
                        method_name = method_parts[i].split("(")[0]
                    # function(internal) or function( internal )
            assert method_name is not None, f"Method name not found in line: {line}"
            return method_name
        return None

    @staticmethod
    def get_classes_used(diffs: dict[str, list[tuple[int, str]]]) -> set[str]:
        new_lines: list[tuple[int, str]] = diffs["added"]
        # Match patterns like: new ClassName() or ClassName.method()
        class_pattern = r"(?:new\s+(\w+)|(\w+)\.[\w<>]+\()"
        classes_referenced = set()
        for _, line in new_lines:
            matches = re.finditer(class_pattern, line)
            for match in matches:
                # Group 1 is from 'new ClassName()'
                # Group 2 is from 'ClassName.method()'
                class_name = match.group(1) or match.group(2)
                if class_name:
                    classes_referenced.add(class_name)
        return classes_referenced

    @staticmethod
    @lru_cache
    def import_name_of(file: ProgramFile) -> Optional[str]:
        for line in file.get_source_code():
            if "package" in line:
                return (
                    line.replace("package ", "").replace(";", "").strip()
                    + "."
                    + file.name.replace(".java", "")
                )

        return None  # default package

    @staticmethod
    @lru_cache
    def fetch_import_names(java_file: ProgramFile) -> set[str]:
        imports: set[str] = set()
        for line in java_file.get_source_code():
            if line.startswith("import"):
                imports.add(line.replace("import ", "").replace(";", "").strip())
            elif "class" in line:
                break
        return imports
