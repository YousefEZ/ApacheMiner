import click


@click.group()
def cli(): ...


@cli.command()
def mine():
    print("Mining...")


@cli.command()
def analyze():
    print("Analyzing...")


if __name__ == "__main__":
    cli()
