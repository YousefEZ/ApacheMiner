import csv

import click
import rich.progress

from .driver import generate_driver
from . import apache_list, github


@click.group()
def cli(): ...


@click.group()
def fetch(): ...


@fetch.command()
@click.argument("output", type=click.Path())
@click.option("--no-attic", is_flag=True, help="Exclude attic projects")
def apache(
    output: str,
    no_attic: bool = False,
):
    driver = generate_driver()
    project_list = apache_list.retrieve_project_list(driver)
    if no_attic:
        project_list = [project for project in project_list if not project.in_attic]

    with open(output, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "repository", "project"])
        with rich.progress.Progress() as progress:
            task = progress.add_task("Fetching projects...", total=len(project_list))
            for project in project_list:
                progress.console.print(f"Fetching GitHub Repository for {project}")
                github_repository = project.fetch_github_project(driver)
                if github_repository:
                    writer.writerow([project.name, github_repository.url])
                    progress.console.print(f"|--> Repository: {github_repository.url}")
                else:
                    progress.console.print("|--> No Repository Found")
                progress.advance(task)

    driver.quit()


@fetch.command(name="github")
@click.argument("url", type=str)
@click.argument("output", type=click.Path())
def github_list(url: str, output: str):
    console = rich.console.Console()
    console.print(f"Fetching GitHub Repository for {url}")
    driver = generate_driver()
    project_list = github.retrieve_project_list(url, driver)

    with open(output, "w") as f:
        with rich.progress.Progress() as progress:
            task = progress.add_task("Writing projects...", total=len(project_list))
            writer = csv.writer(f)
            writer.writerow(["name", "repository"])
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
