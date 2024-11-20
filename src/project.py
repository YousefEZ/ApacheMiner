from dataclasses import dataclass


@dataclass(frozen=True)
class GithubProject:
    name: str
    url: str
