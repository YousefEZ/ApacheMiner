from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, element
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from .project import GithubProject

__all__ = ("ApacheProject", "retrieve_project_list")

BASE_URL = "https://projects.apache.org"
PROJECT_LIST = f"{BASE_URL}/projects.html"


@dataclass(frozen=True)
class ApacheProject:
    name: str
    path_segment: str

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self.path_segment}"

    def __repr__(self):
        return f"{self.name}: ({self.url})"

    @property
    def in_attic(self):
        return "attic" in self.name

    def fetch_github_project(self, driver: webdriver.Chrome) -> Optional[GithubProject]:
        driver.get(self.url)
        WebDriverWait(driver, 20).until(
            lambda driver: "Loading data, please wait..."
            not in driver.find_element(By.ID, "contents").text
        )

        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")
        git_repository = list(
            filter(lambda li: "Git repository" in li.text, soup.find_all("li"))
        )
        if len(git_repository) == 0:
            return None
        tag = git_repository[0].find("a")
        assert isinstance(tag, element.Tag), "Git repository is not a tag"
        link = tag["href"]
        assert isinstance(link, str), "Git repository link is not a string"
        return GithubProject(self.name, link)


def retrieve_project_list(driver: webdriver.Chrome) -> list[ApacheProject]:
    driver.get(PROJECT_LIST)
    WebDriverWait(driver, 10).until(
        lambda driver: "Loading data, please wait..."
        not in driver.find_element(By.ID, "list").text
    )
    html = driver.page_source

    soup = BeautifulSoup(html, "html.parser")
    projects = []
    project_list_raw = soup.find("div", id="list")
    assert project_list_raw is not None, "No project list found"
    assert isinstance(project_list_raw, element.Tag), "Project list is not a tag"

    for project in project_list_raw.find_all("a"):
        projects.append(ApacheProject(project.text, project["href"]))

    return projects
