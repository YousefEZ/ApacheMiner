import csv
import os
import re
import tempfile
from typing import Optional, ParamSpec

import click
import git
import rich.progress
import rich.table
import rich.theme

from src import apache_list, driller, github
from src.discriminators import transaction
from src.discriminators.binding.factory import Strategies, strategy_factory
from src.discriminators.binding.repository import JavaRepository
from src.discriminators.factory import DiscriminatorTypes, discriminator_factory
from src.driver import generate_driver
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
        project_list = github.retrieve_project_list(url, driver)

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
def repository(url: str, output: str) -> None:
    with rich.progress.Progress(console=console) as progress:
        driller.drill_repository(url, output, progress)


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
def repositories(
    input_file: str,
    output: tuple[str, str],
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
                row["repository"], output[1].replace(output[0], row["name"]), progress
            )


@cli.command()
@click.option("--input", "-i", "_input_file", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--map", "-m", "map_file", type=click.Path(), required=True)
def transform(_input_file: str, output: str, map_file: str) -> None:
    with open(_input_file, "r") as commit_file:
        transaction_log = transaction.TransactionLog.from_commit_data(
            list(csv.DictReader(commit_file))
        )
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
@click.option("--url", "-u", required=True)
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
@click.option("--repo", "-r", type=click.Path(), default="commits.csv")
def discriminate(
    url: str, discriminator_type: DiscriminatorTypes, binding: Strategies, repo: str
) -> None:
    cwd = os.path.join(os.getcwd(), "repositories")
    directory_name = url.split("/")[-1].replace(".git", "")
    dir = os.path.join(cwd, directory_name)
    if not os.path.exists("repositories"):
        console.print("Creating path")
        os.makedirs(dir)

    path = os.path.join(dir, repo)
    if not os.path.exists(path):
        with rich.progress.Progress() as progress:
            console.print(f"Cloning repository from {url}")
            git.Repo.clone_from(url=url, to_path=dir)

            console.print("Repository cloned")
            console.print(f"Drilling repository from {dir}")

            driller.drill_repository(dir, path, progress)
            console.print("Repository drilled")
            progress.stop()

    with open(path, "r") as f:
        transaction_log = transaction.TransactionLog.from_commit_data(
            list(csv.DictReader(f))
        )

    binding_strategy = strategy_factory[binding](JavaRepository(dir))
    discriminator = discriminator_factory[discriminator_type](
        transaction_log, binding_strategy
    )
    statistics = discriminator.statistics

    console.print(statistics.output())


cli.add_command(fetch)
cli.add_command(drill)
cli.add_command(analyze)

if __name__ == "__main__":
    cli()
