import os
from functools import wraps
from typing import Callable, Optional, ParamSpec, TypeVar

import requests
from rich.console import Console

P = ParamSpec("P")
T = TypeVar("T")

console = Console()


def download_spmf() -> None:
    if not os.path.exists(".spmf"):
        console.print(":sparkles: creating .spmf directory", emoji=True)
        os.mkdir(".spmf")
    with console.status(":inbox_tray: Downloading SPMF..."):
        response = requests.get(
            "http://www.philippe-fournier-viger.com/spmf/spmf.jar",
            allow_redirects=True,
        )
        with open(".spmf/spmf.jar", "wb") as spmf:
            spmf.write(response.content)
    console.print(":heavy_check_mark: SPMF Downloaded", emoji=True)


def is_spmf_installed() -> bool:
    return os.path.exists(".spmf/spmf.jar")


def ask_to_download_spmf() -> bool:
    console.print(":x: SPMF [bold red]not found[/bold red]", emoji=True)
    result = console.input(
        ":inbox_tray: Would you like to download SPMF now? (y/n)", emoji=True
    )
    return result.lower() == "y"


def check_spmf(function: Callable[P, T]) -> Callable[P, Optional[T]]:
    @wraps(function)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
        if not is_spmf_installed():
            if not ask_to_download_spmf():
                return None
            download_spmf()
        return function(*args, **kwargs)

    return wrapper


def run_spmf(algorithm: str, *args: str) -> bool:
    process = os.system(f"java -jar .spmf/spmf.jar run {algorithm} {' '.join(args)}")
    if process != 0:
        console.print(f":x: {algorithm} [bold red]failed[/bold red]", emoji=True)
    return process == 0
