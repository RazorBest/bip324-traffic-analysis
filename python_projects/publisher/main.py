#!/bin/python

import os
import requests
import subprocess
import sys
import time

def publish_service(metrics_url: str, github_url: str, path_secret_key: str, gitname: str, gitemail):
    env = {"GIT_SSH_COMMAND": "ssh -o StrictHostKeyChecking=no"}
    subshell_command = f"ssh-add '{path_secret_key}'; git clone '{github_url}' project"
    subprocess.run(["ssh-agent", "bash", "-c", subshell_command], env=env, check=True) 
    os.chdir("./project")

    subprocess.run(["git", "config", "user.name", gitname], check=True)
    subprocess.run(["git", "config", "user.email", gitemail], check=True)

    while True:
        r = requests.get(metrics_url)
        if r.status_code == 200:
            print(r.text)
            with open("index.html", "w") as file:
                file.write(r.text)
            subprocess.run(["git", "add", "index.html"], check=True) 
            subprocess.run(["git", "commit", "-m", '"update index.html"'], check=True) 

            subshell_command = f"ssh-add '{path_secret_key}'; git push origin"
            subprocess.run(["ssh-agent", "bash", "-c", subshell_command], env=env) 
        else:
            print(f"Request error: {r}")

        # Sleep for 5 minutes
        time.sleep(60 * 5)


def main():
    if len(sys.argv) < 6:
        print("Usage: python3 main.py <metrics_url> <github_publish_url> <path_to_secret_key>")
        return 1

    metrics_url = sys.argv[1]
    github_url = sys.argv[2]
    path_secret_key = sys.argv[3]
    gitname = sys.argv[4]
    gitemail = sys.argv[5]

    publish_service(metrics_url, github_url, path_secret_key, gitname, gitemail)

    return 0

if __name__ == "__main__":
    exit(main())
