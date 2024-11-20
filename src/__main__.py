import csv

import click
import rich.progress

from . import apache_list


@click.group()
def cli(): ...


@cli.command()
@click.argument("output", type=click.Path())
@click.option("--no-attic", is_flag=True, help="Exclude attic projects")
def fetch(
    output: str,
    no_attic: bool = False,
):
    project_list = apache_list.retrieve_project_list()
    if no_attic:
        project_list = [
            project for project in project_list if not project.in_attic
        ]
    driver = apache_list.generate_driver()

    with open(output, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "repository", "project"])
        with rich.progress.Progress() as progress:
            task = progress.add_task(
                "Fetching projects...", total=len(project_list)
            )
            for project in project_list:
                progress.console.print(
                    f"Fetching GitHub Repository for {project}"
                )
                repository = project.fetch_repository(driver)
                writer.writerow([project.name, repository, project.url])
                progress.console.print(
                    f"|--> Repository: {repository}"
                    if repository
                    else "|--> No Repository Found"
                )
                progress.advance(task)

    driver.quit()


@cli.command()
def analyze():
    print("Analyzing...")


if __name__ == "__main__":
    cli()
