import csv
import re

import click
import rich.progress
import rich.theme

from . import apache_list, driller, github, transaction
from .driver import generate_driver

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

@click.group()
def transform(): ...

@transform.command(name="list")
@click.option("--input", "-i", "_input_file", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--map", "-m", "map_file", type=click.Path(), required=True)
def transform_list(_input_file: str, output: str, map_file: str) -> None:
    result = transaction.convert_into_transaction(_input_file)
    with open(output, "w") as writer:
        for changes in result.transactions:
            writer.write(" ".join(map(str, changes)) + "\n")

    with open(map_file, "w") as map_writer:
        for key, value in result.maps.names.items():
            map_writer.write(f"{key}: {value}\n")

@transform.command(name="sequence")
@click.option("--input", "-i", "_input_file", type=click.Path(), required=True)
@click.option("--output", "-o", type=click.Path(), required=True)
@click.option("--map", "-m", "map_file", type=click.Path(), required=True)
def transform_spm(_input_file: str, output: str, map_file: str) -> None:
    lines, map = transaction.convert_for_spm(_input_file)
    with open(output, "w") as writer:
        for line in lines:
            writer.write(str(line) + "\n")
    
    with open(map_file, "w") as map_writer:
        for key, value in map:
            map_writer.write(f"{key}: {value}\n")

@cli.command()
def analyze():
    print("Analyzing...")


cli.add_command(fetch)
cli.add_command(drill)
cli.add_command(transform)

if __name__ == "__main__":
    cli()
