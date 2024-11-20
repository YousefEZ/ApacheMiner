from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

from . import project

GITHUB_URL = "https://github.com"
TITLE_DATA_TEST_ID = "listitem-title-link"
CUSTOM_ATTRIBUTE = "data-testid"


def contains_repositories(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    return soup.find("a", {CUSTOM_ATTRIBUTE: TITLE_DATA_TEST_ID}) is not None


def scrape_github_projects(html: str) -> list[project.GithubProject]:
    soup = BeautifulSoup(html, "html.parser")
    projects = []

    # all project links have this attribute
    tags = soup.find_all("a", {CUSTOM_ATTRIBUTE: TITLE_DATA_TEST_ID})
    assert tags is not None, "No project list found"

    for tag in tags:
        name = tag.text
        url = tag["href"]
        projects.append(project.GithubProject(name, GITHUB_URL + url))

    return projects


def next_page(url: str, current_page: int) -> str:
    if "page" not in url:
        return url + ("?page=2" if "?" not in url else "&page=2")
    return url.replace(f"page={current_page}", f"page={current_page + 1}")


def retrieve_project_list(
    url: str, driver: webdriver.Chrome
) -> list[project.GithubProject]:
    repositories = []
    current_page = 1
    while True:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

        html = driver.page_source
        new_repositories = scrape_github_projects(html)
        if not new_repositories:
            return repositories
        repositories.extend(new_repositories)
        url = next_page(url, current_page)
        current_page += 1
