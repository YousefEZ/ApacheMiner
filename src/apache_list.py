from typing import Optional

from bs4 import BeautifulSoup, element
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

BASE_URL = "https://projects.apache.org"
PROJECT_LIST = f"{BASE_URL}/projects.html"


def _generate_options():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    return options


def generate_driver():
    options = _generate_options()
    driver = webdriver.Chrome(options=options)
    return driver


class Project:
    def __init__(self, name: str, url: str):
        self._name = name
        self._url = url

    @property
    def name(self) -> str:
        return self._name

    @property
    def url(self) -> str:
        return f"{BASE_URL}/{self._url}"

    def __repr__(self):
        return f"{self.name}: ({self.url})"

    @property
    def in_attic(self):
        return "attic" in self._name

    def fetch_repository(self, driver: webdriver.Chrome) -> Optional[str]:
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
        return link


def retrieve_project_list() -> list[Project]:
    driver = generate_driver()
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
    assert isinstance(
        project_list_raw, element.Tag
    ), "Project list is not a tag"

    for project in project_list_raw.find_all("a"):
        projects.append(Project(project.text, project["href"]))

    driver.quit()
    return projects
