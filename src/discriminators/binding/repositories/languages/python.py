import re
from functools import lru_cache
from typing import Optional

from src.discriminators.binding.file_types import ProgramFile
from src.discriminators.binding.repositories.languages.language import Language


class PythonLanguage(Language):
    SUFFIX: str = ".py"

    @staticmethod
    def get_defined_method(line: str) -> Optional[str]:
        pattern = r"^\s*(def)" + r"?[\w<>[\],\s]+\s+\w+\s*\([^)]*\)"
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
        # Match patterns like: ClassName() or ClassName.method()
        class_pattern = r"(\w+)\(\)|(\w+)\.[\w]+\("
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
        return file.name.replace(".py", "")

    @staticmethod
    def is_import(line: str) -> bool:
        "via regex, checks if it follows the form import module_name(.module_name)*"
        return bool(re.match(r"import \w+(\.\w+)*", line)) or bool(
            re.match(r"from \w+(\.\w+)* import \w+(\s*,\s*\w+)*", line)
        )

    @staticmethod
    @lru_cache
    def fetch_import_names(java_file: ProgramFile) -> set[str]:
        imports: set[str] = set()
        for line in filter(PythonLanguage.is_import, java_file.get_source_code()):
            if line.startswith("import"):
                # e.g. import src.module
                imports.add(line.replace("import ", "").split(".")[-1])
            elif line.startswith("from"):
                # e.g. from src.package import module
                # e.g. from src.module import module, class
                file_imports = line.split(" import ")
                module = file_imports[0].split(".")[-1]
                imports.add(module)

                for module in file_imports[1].split(", "):
                    imports.add(module)
        return imports


if __name__ == "__main__":
    test_string = "def test_method(self, arg1, arg2):"
    print(PythonLanguage.get_defined_method(test_string))

    used_string = "ClassName.method()"
    print(PythonLanguage.get_classes_used({"added": [(0, used_string)]}))

    alternative_used_string = "ClassName()"
    print(PythonLanguage.get_classes_used({"added": [(0, alternative_used_string)]}))
