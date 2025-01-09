import csv

input_csv = '/Users/sachilad/Documents/GitHub/ApacheMiner/mining_repos/apache_projects_commits_final.csv'
output_nonreverse_txt = 'repos_sachi_nonreverse.txt'
output_reverse_txt = 'repos_sachi_reversable.txt'

repositories_nonreverse = []
repositories_reverse = []

# Read the CSV file and collect repositories where Assigned is 'S'
with open(input_csv, mode='r') as csv_file:
    csv_reader = csv.DictReader(csv_file)
    for row in csv_reader:
        if row['Assgined'] == 'S':
            if row['reversable'] == 'FALSE':
                repositories_nonreverse.append(row)
            elif row['reversable'] == 'TRUE':
                repositories_reverse.append(row)

# Sort the repositories by the number of commits in ascending order
repositories_nonreverse.sort(key=lambda x: int(x['Commits']))
repositories_reverse.sort(key=lambda x: int(x['Commits']))

# Write the sorted non-reversible repositories to a text file
with open(output_nonreverse_txt, mode='w') as txt_file:
    for repo in repositories_nonreverse:
        txt_file.write(f"https://github.com/apache/{repo['Repository']}\n")

# Write the sorted reversible repositories to a text file
with open(output_reverse_txt, mode='w') as txt_file:
    for repo in repositories_reverse:
        txt_file.write(f"https://github.com/apache/{repo['Repository']}\n")
