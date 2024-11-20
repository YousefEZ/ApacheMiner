from typing import Iterable
import random
from itertools import chain

import hypothesis
import hypothesis.strategies

from src.github import (
    CUSTOM_ATTRIBUTE,
    TITLE_DATA_TEST_ID,
    scrape_github_projects,
    next_page,
)


def test_next_page_no_filter():
    url = "https://github.com/orgs/apache/repositories"
    assert next_page(url) == f"{url}?page=2"


def test_next_page_no_filter_second_page():
    url = "https://github.com/orgs/apache/repositories?page=2"
    assert next_page(url) == f"{url[:-1]}3"


def test_next_page_with_filter():
    url = "https://github.com/orgs/apache/repositories?q=language%3AC%2B%2B"
    assert next_page(url) == f"{url}&page=2"


def test_next_page_with_filter_second_page():
    url = "https://github.com/orgs/apache/repositories?q=language%3AC%2B%2B&page=2"
    assert next_page(url) == f"{url[:-1]}3"


def generate_positive_hyperlinks(number: int) -> Iterable[str]:
    for _ in range(number):
        yield f"<a {CUSTOM_ATTRIBUTE}='{TITLE_DATA_TEST_ID}' href='/orgs/apache/repositories'>Apache</a>"
    return None


def generate_missing_attribute_hyperlinks(number: int) -> Iterable[str]:
    for _ in range(number):
        yield "<a href='/orgs/apache/repositories'>Apache</a>"


def generate_incorrect_attribute_value_hyperlinks(number: int) -> Iterable[str]:
    for _ in range(number):
        yield f"<a {CUSTOM_ATTRIBUTE}='INCORRECT' href='/orgs/apache/repositories'>Apache</a>"


def generate_random_html(
    positive: int, missing: int, incorrect: int, rand: random.Random
) -> tuple[str, tuple[int, int, int]]:
    hyperlinks = list(
        chain(
            generate_positive_hyperlinks(positive),
            generate_missing_attribute_hyperlinks(missing),
            generate_incorrect_attribute_value_hyperlinks(incorrect),
        )
    )

    rand.shuffle(hyperlinks)
    return "<html>" + "".join(hyperlinks) + "</html>", (
        positive,
        missing,
        incorrect,
    )


@hypothesis.given(
    hypothesis.strategies.builds(
        generate_random_html,
        hypothesis.strategies.integers(min_value=0, max_value=10),
        hypothesis.strategies.integers(min_value=0, max_value=10),
        hypothesis.strategies.integers(min_value=0, max_value=10),
        hypothesis.strategies.randoms(),
    )
)
def test_content_parsing(html_and_counts: tuple[str, tuple[int, int, int]]):
    html, counts = html_and_counts
    projects = scrape_github_projects(html)
    assert len(projects) == counts[0]
