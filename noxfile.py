import nox


@nox.session
def tests(session):
    session.run("pytest", external=True)


@nox.session
def lint(session):
    session.install("flake8")
    session.run("flake8", "src", "tests")


@nox.session
def isort(session):
    session.install("isort")
    session.run("isort", "src", "tests")


@nox.session
def formatting(session):
    session.install("black")
    session.run("black", "src", "tests")


@nox.session
def type_check(session):
    session.run("mypy", "src", "tests", external=True)
