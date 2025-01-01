import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import os
from bs4 import BeautifulSoup
import concurrent.futures
import time

class MergeFinder:

    def __init__(self, repo_name: str, branch='trunk'):
        #TODO change repo_name to url and extract name
        self.repo_name = repo_name
        self.branch = branch
        load_dotenv()
        self.username = os.getenv('GITHUB_USERNAME')
        self.token = os.getenv('GITHUB_TOKEN')
    
    # Function to fetch pull requests for a specific page
    def _fetch_pull_requests(self, page: int) -> list:
        url_api = f'https://api.github.com/repos/{self.repo_name}/pulls'
        params = {'state': 'closed', 'base': self.branch, 'page': page}
        response = requests.get(url_api, auth=HTTPBasicAuth(self.username, self.token), params=params)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to retrieve commits: {response.status_code}")
            return []

    def _find_number_pages(self) -> int:

        url_bs = f'https://github.com/{self.repo_name}/pulls?q=is%3Aclosed'

        response_bs = requests.get(url_bs)
        soup = BeautifulSoup(response_bs.content, 'html.parser')
        
        # Find the element with the `data-total-pages` attribute
        page_count_element = soup.find('em', {'class': 'current'})
        
        if page_count_element and 'data-total-pages' in page_count_element.attrs:
            total_pages = int(page_count_element['data-total-pages'])
            print(f'Total number of pages: {total_pages}')
        else:
            print('Could not find the page count element.')
            total_pages = 1  # Default to 1 if the page count element is not found
        return total_pages

    def get_merge_commits(self) -> list:
        """
        Unsafe version, could raise SSLError
        """
  
        total_pages = self._find_number_pages()

        # List to store merge commit SHAs
        commits_merge = []

        # Fetch pull requests concurrently
        with concurrent.futures.ThreadPoolExecutor() as executor:
            pages = range(total_pages)
            results = executor.map(self._fetch_pull_requests, pages)
            for result in results:
                for commit in result:
                    if 'merge_commit_sha' in commit:
                        commits_merge.append(commit['merge_commit_sha'])

        return commits_merge
    
    #optional
    def safe_get_merge_commits(self, tries=3) -> list:
        """
        Recomneded version to use, attempts to get the list the specified times in tries variable. Return None if unsuscessful
        """
        tries = abs(tries)
        merge_commits = None
        while 0 < tries:
            try:
                merge_commits = self.get_merge_commits()
            except: 
                tries-=1
                print("failed, retry in 2s")
                time.sleep(2)
        return merge_commits


# Example usage
repo_name = 'apache/kafka'
branch_name = 'trunk'
while True:
    try:
        t = time.time()
        finder = MergeFinder(repo_name=repo_name,branch=branch_name)
        merge_commits = finder.get_merge_commits()
        print(f"{time.time()-t}s")
        break
    except: 
        print("failed, retry in 2s")
        time.sleep(2)
print('795390a3c856c98eb4934ddc996f35693bed8ac5' in merge_commits)
print(len(merge_commits))
