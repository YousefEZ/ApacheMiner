import csv
import re

import click
import rich.progress
import rich.theme

from . import apache_list, github
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


@fetch.command()
@click.argument("output", type=click.Path())
@click.option("--no-attic", is_flag=True, help="Exclude attic projects")
@click.option("--no-incubating", is_flag=True, help="Exclude incubating projects")
@click.option("--no-dormant", is_flag=True, help="Exclude incubating projects")
def apache(
    output: str,
    no_attic: bool = False,
    no_incubating: bool = False,
    no_dormant: bool = False,
):
    driver = generate_driver()
    project_list = apache_list.retrieve_project_list(driver)
    if no_attic:
        project_list = [project for project in project_list if not project.in_attic]
    if no_incubating:
        project_list = [project for project in project_list if not project.in_incubator]
    if no_dormant:
        project_list = [project for project in project_list if not project.is_dormant]

    with open(output, "w") as f:
        writer = csv.writer(f)
        writer.writerow(HEADER)
        with rich.progress.Progress(console=console) as progress:
            task = progress.add_task(
                ":rocket: Fetching projects...", total=len(project_list)
            )
            for project in project_list:
                progress.console.print(
                    f":mag_right: Fetching GitHub Repository for {project.name}",
                    emoji=True,
                )
                github_repository = project.fetch_github_project(driver)
                if github_repository:
                    writer.writerow([project.name, github_repository.url])
                    progress.console.print(
                        "|--> :heavy_check_mark:  Repository [success]Found[/success]",
                        emoji=True,
                    )
                else:
                    progress.console.print(
                        "|--> :x: Repository [danger]Not Found[/danger]", emoji=True
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

    with open(output, "w") as f:
        with rich.progress.Progress() as progress:
            task = progress.add_task(
                ":pencil2:  Writing projects...", emoji=True, total=len(project_list)
            )
            writer = csv.writer(f)
            writer.writerow(HEADER)
            for project in project_list:
                writer.writerow([project.name, project.url])
                progress.advance(task)
    driver.quit()


@cli.command()
def analyze():
    print("Analyzing...")


cli.add_command(fetch)
if __name__ == "__main__":
    cli()
