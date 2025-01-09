import os
import subprocess

input_file = '/Users/sachilad/Documents/GitHub/ApacheMiner/mining_repos/repos_sachi_nonreverse_copy.txt'
discriminator = 'before_after'
binding = 'import'
results_dir = '/Users/sachilad/Documents/GitHub/ApacheMinerLocal/results/before_after'

# Ensure the results directory exists
os.makedirs(results_dir, exist_ok=True)

with open(input_file, 'r') as file:
    lines = file.readlines()
    total_repos = len(lines)

    for index, line in enumerate(lines):
        repo_url = line.strip()
        if repo_url:
            project_name = repo_url.split('/')[-1]
            repo_path = f'/Users/sachilad/Documents/GitHub/ApacheMinerLocal/repos/{project_name}'
            result_file = os.path.join(results_dir, f'results_{discriminator}_{project_name}.csv')
            
            print(f"Processing project {index + 1}/{total_repos}: {project_name}")

            command = [
                'poetry', 'run', 'cli', 'discriminate',
                '--path', repo_path,
                '--discriminator', discriminator,
                '--binding', binding
            ]
            
            with open(result_file, 'w') as output_file:
                subprocess.run(command, stdout=output_file)
            
            print(f"Completed project {index + 1}/{total_repos}: {project_name}")

input_file = '/Users/sachilad/Documents/GitHub/ApacheMiner/mining_repos/repos_sachi_reversable.txt'
discriminator = 'before_after'
binding = 'import'
results_dir = '/Users/sachilad/Documents/GitHub/ApacheMinerLocal/results/before_after'

# Ensure the results directory exists
os.makedirs(results_dir, exist_ok=True)

with open(input_file, 'r') as file:
    lines = file.readlines()
    total_repos = len(lines)

    for index, line in enumerate(lines):
        repo_url = line.strip()
        if repo_url:
            project_name = repo_url.split('/')[-1]
            repo_path = f'/Users/sachilad/Documents/GitHub/ApacheMinerLocal/repos/{project_name}'
            result_file = os.path.join(results_dir, f'results_{discriminator}_{project_name}.csv')
            
            print(f"Processing project {index + 1}/{total_repos}: {project_name}")

            command = [
                'poetry', 'run', 'cli', 'discriminate',
                '--path', repo_path,
                '--discriminator', discriminator,
                '--binding', binding
            ]
            
            with open(result_file, 'w') as output_file:
                subprocess.run(command, stdout=output_file)
            
            print(f"Completed project {index + 1}/{total_repos}: {project_name}")
