import csv
import os
import re
import sys
import tempfile
from itertools import chain
from typing import Optional, ParamSpec, cast

import click
import git
import pydriller
import rich.progress
import rich.table
import rich.theme

from src import apache_list, driller, github_scraper
from src.discriminators import transaction
from src.discriminators.binding.factory import Strategies, strategy_factory
from src.discriminators.binding.repositories.factory import repository_factory
from src.discriminators.binding.repositories.languages.factory import (
    get_repository_language,
)
from src.discriminators.factory import DiscriminatorTypes, discriminator_factory
from src.discriminators.file_types import FileChanges
from src.driver import generate_driver
from src.git_progress import CloneProgress
from src.spmf.association import analyze_apriori, apriori

P = ParamSpec("P")

HEADER = ["name", "repository"]

theme = rich.theme.Theme(
    {
        "info": "cyan",
        "danger": "bold red",
        "warning": "bold yellow",
        "success": "bold green",
    }
)
console = rich.console.Console(theme=theme)


@click.group()
def cli(): ...


@click.group()
def fetch(): ...


@cli.command()
@click.option("--dir", "-d", type=click.Path(), required=True)
@click.argument("targets", type=str, nargs=-1)
def clone(dir: str, targets: list[str]) -> None:
    stdin_targets = (
        click.get_text_stream("stdin").read().splitlines()
        if not sys.stdin.isatty()
        else tuple()
    )
    for idx, repo in enumerate(
        (
            target
            if pydriller.Repository._is_remote(target)
            else f"{github_scraper.GITHUB_URL}/{target}"
        )
        for target in chain(targets, stdin_targets)
    ):
        name = repo.split(".git")[0].split("/")[-1]
        console.print(
            f"Cloning repository {name} [{idx+1}/{len(targets)+len(stdin_targets)}]"
        )
        with CloneProgress() as progress:
            git.Repo.clone_from(
                url=repo, progress=progress, to_path=os.path.join(dir, name)
            )


def print_if_not_silent(message: str, *, silent: bool = False):
    if not silent:
        console.print(message, emoji=True)


@fetch.command()
@click.argument("output", type=click.Path())
@click.option("--no-attic", is_flag=True, help="Exclude attic projects")
@click.option("--no-incubating", is_flag=True, help="Exclude incubating projects")
@click.option("--no-dormant", is_flag=True, help="Exclude dormant projects")
@click.option("--silent", "-s", is_flag=True, help="Do not print projects")
def apache(
    output: str,
    no_attic: bool = False,
    no_incubating: bool = False,
    no_dormant: bool = False,
    silent: bool = False,
):
    driver = generate_driver()
    project_list = apache_list.retrieve_project_list(driver)
    if no_attic:
        project_list = [project for project in project_list if not project.in_attic]
    if no_incubating:
        project_list = [project for project in project_list if not project.in_incubator]
    if no_dormant:
        project_list = [project for project in project_list if not project.is_dormant]

    with open(output, "w") as f, rich.progress.Progress(console=console) as progress:
        writer = csv.writer(f)
        writer.writerow(HEADER)

        task = progress.add_task(
            ":rocket: Fetching projects...", total=len(project_list)
        )

        for project in project_list:
            print_if_not_silent(
                f":mag_right: Fetching GitHub Repository for {project.name}",
                silent=silent,
            )
            github_repository = project.fetch_github_project(driver)
            if github_repository:
                writer.writerow([project.name, github_repository.url])

            print_if_not_silent(
                (
                    "|-> :heavy_check_mark:  Repository [success]Found[/success]"
                    if github_repository
                    else "|-> :x: Repository [danger]Not Found[/danger]"
                ),
                silent=silent,
            )
            progress.advance(task)

    driver.quit()


@fetch.command(name="github")
@click.argument("url", type=str)
@click.argument("output", type=click.Path())
def github_list(url: str, output: str):
    console = rich.console.Console()

    regex = r"https://github\.com/.+/repositories.*"
    if not re.match(regex, url):
        console.print(":x: Invalid GitHub URL", emoji=True, style="bold red")
        return
    with console.status(f":mag_right: Fetching GitHub Repository for {url}"):
        driver = generate_driver()
        project_list = github_scraper.retrieve_project_list(url, driver)

    console.print(f"Found [cyan]{len(project_list)}[/cyan] projects")

    with open(output, "w") as f, rich.progress.Progress() as progress:
        task = progress.add_task(
            ":pencil2:  Writing projects...", emoji=True, total=len(project_list)
        )
        writer = csv.writer(f)
        writer.writerow(HEADER)
        for project in project_list:
            writer.writerow([project.name, project.url])
            progress.advance(task)
    driver.quit()


@click.group()
def drill(): ...


@drill.command()
@click.option("--url", "-u", type=str, required=True)
@click.option("--output", "-o", type=str, required=True)
@click.option("--reverse-squash", "-e", type=bool, is_flag=True, default=False)
def repository(url: str, output: str, reverse_squash: bool) -> None:
    with rich.progress.Progress(console=console) as progress:
        driller.drill_repository(url, output, progress, reverse_squash)


@drill.command()
@click.option("--input", "-i", "input_file", type=click.Path(), required=True)
@click.option(
    "--output-pattern",
    "-o",
    "output",
    nargs=2,
    help="match pattern followed by pattern e.g. %s outputs/commits_%s.csv",
    required=True,
)
@click.option("--reverse-squash", "-e", type=bool, is_flag=True, default=False)
def repositories(
    input_file: str,
    output: tuple[str, str],
    reverse_squash: bool,
) -> None:
    with open(input_file, "r") as f, rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        *rich.progress.Progress.get_default_columns(),
        console=console,
    ) as progress:
        reader = csv.DictReader(f)
        rows = list(reader)
        console.print(f"Found [cyan]{len(rows)}[/cyan] repositories")
        task_id = progress._task_index
        for idx, row in enumerate(progress.track(rows)):
            progress.tasks[task_id].description = (
                f"Drilling Repositories [{idx+1}/{len(rows)}]..."
            )
            driller.drill_repository(
                row["repository"],
                output[1].replace(output[0], row["name"]),
                progress,
                reverse_squash,
            )


@cli.command()
@click.option("--input", "-i", "_input_file", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--map", "-m", "map_file", type=click.Path(), required=True)
def transform(_input_file: str, output: str, map_file: str) -> None:
    with open(_input_file, "r") as commit_file:
        data = cast(list[FileChanges], list(csv.DictReader(commit_file)))
        transaction_log = transaction.TransactionLog.from_commit_log(data)
    with open(output, "w") as transactions, open(map_file, "w") as mapping:
        transactions.write(transaction_log.transactions.model_dump_json(indent=2))
        mapping.write(transaction_log.mapping.model_dump_json(indent=2))


@click.group()
def analyze(): ...


@analyze.command()
@click.option("--transactions", "-t", type=click.Path(), required=True)
@click.option("--map", "-m", "map_file", type=click.Path(), required=True)
@click.option("--display", "-d", "display", is_flag=True, default=False)
@click.option("--limit", "-l", type=int, default=2)
@click.option("--must-have", "-mh", type=str)
@click.option("--dump-output", "-do", "output_dir", type=click.Path())
@click.option("--percentage", "-p", type=float, default=0.75)
def association(
    transactions: str,
    map_file: str,
    display: bool,
    limit: int,
    must_have: str,
    output_dir: Optional[str],
    percentage: float,
) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        output_file: str

        if output_dir:
            ensure_dir = os.path.dirname(output_dir)
            if not os.path.exists(ensure_dir):
                os.makedirs(ensure_dir)
            output_file = f"{output_dir}/output.txt"
        else:
            output_file = f"{temp_dir}/output.txt"
        # storing it in file, so it doesn't have to be all in memory
        apriori(transactions, output_file, percentage)

        results = analyze_apriori(output_file, map_file, limit, must_have)

        if display:
            table = rich.table.Table(title="Associated Files")
            for i in range(results.largest_associated):
                table.add_column(f"File {i+1}", justify="center")
            for associated in results.associated_files:
                table.add_row(
                    *associated,
                    *["-" for _ in range(results.largest_associated - len(associated))],
                )
            console.print(table)
        else:
            print(results.associated_files)


@cli.command()
@click.option("--url", "-u", type=str)
@click.option("--path", "-p", type=click.Path())
@click.option(
    "--discriminator",
    "-d",
    "discriminator_type",
    type=click.Choice(list(discriminator_factory.keys())),
    required=True,
)
@click.option(
    "--binding", "-b", type=click.Choice(list(strategy_factory.keys())), required=True
)
@click.option("--reverse-squash", "-e", type=bool, is_flag=True, default=False)
@click.option("--save", "-s", is_flag=True, help="Save the repository for reuse")
def discriminate(
    url: Optional[str],
    path: Optional[str],
    discriminator_type: DiscriminatorTypes,
    binding: Strategies,
    reverse_squash: bool,
    save: bool,
) -> None:
    assert url or path, "Either URL or Path must be provided"

    if url:
        if save:
            assert path, "Path must be provided to save the repository"
            assert not os.path.exists(path), "Path must not exist"
            assert url, "URL must be provided to clone the repository"

            console.print(f"Cloning repository from {url}")
            os.makedirs(path)
            git.Repo.clone_from(url=url, to_path=path)
            console.print("Repository cloned")

            run_discriminator(path, discriminator_type, binding, reverse_squash)
        else:
            with tempfile.TemporaryDirectory() as dir:
                console.print(f"Cloning repository from {url}")
                git.Repo.clone_from(url=url, to_path=dir)
                console.print("Repository cloned")

                run_discriminator(dir, discriminator_type, binding, reverse_squash)
    elif path:
        run_discriminator(path, discriminator_type, binding, reverse_squash)


def run_discriminator(
    dir: str,
    discriminator_type: DiscriminatorTypes,
    binding: Strategies,
    reverse_squash: bool,
) -> None:
    OUTPUT_FILE = f"{dir}/commits{'_squash_reversed' if reverse_squash else ''}.csv"
    if not os.path.exists(OUTPUT_FILE):
        console.print(f"Drilling repository from {dir}")
        with rich.progress.Progress() as progress:
            driller.drill_repository(dir, OUTPUT_FILE, progress, reverse_squash)
        console.print("Repository drilled")

    with open(OUTPUT_FILE, "r") as f:
        data = cast(list[FileChanges], list(csv.DictReader(f)))

    repo_info = driller.get_repo_information(dir)
    language = get_repository_language(f"{repo_info.org}/{repo_info.name}")
    console.print(f"Repository language is {language}")
    repository = repository_factory[language](dir)
    binding_strategy = strategy_factory[binding](repository)
    discriminator = discriminator_factory[discriminator_type](data, binding_strategy)
    statistics = discriminator.statistics

    console.print(statistics.output())


cli.add_command(fetch)
cli.add_command(drill)
cli.add_command(analyze)

if __name__ == "__main__":
    cli()
