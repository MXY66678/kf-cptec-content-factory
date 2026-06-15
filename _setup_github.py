#!/usr/bin/env python3
"""GitHub repo setup script — creates repo and pushes code."""

import getpass
import subprocess
import sys

import httpx

GIT_DIR = "/Users/mac/Documents/Codex/kf-cptec-content-factory"
REPO_NAME = "kf-cptec-content-factory"
REPO_DESC = "KF CPTEC Multi-AI Content Factory — automated SEO blog, Amazon listing, and video retrieval pipeline"


def run_git(cmd: list[str], cwd: str = GIT_DIR) -> subprocess.CompletedProcess:
    return subprocess.run(["git"] + cmd, capture_output=True, text=True, cwd=cwd)


def main():
    token = getpass.getpass("Paste your GitHub Personal Access Token: ")
    username = "MXY66678"

    # 1. Create repo via GitHub API
    print(f"Creating GitHub repo: {REPO_NAME} ...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    data = {
        "name": REPO_NAME,
        "description": REPO_DESC,
        "private": False,
        "auto_init": False,
    }

    with httpx.Client() as client:
        resp = client.post(
            "https://api.github.com/user/repos",
            headers=headers,
            json=data,
        )

    if resp.status_code == 201:
        print("Repository created successfully!")
    elif resp.status_code == 422:
        print("Repository may already exist. Trying to push...")
    else:
        print(f"Error: {resp.status_code} - {resp.text}")
        sys.exit(1)

    # 2. Set remote and push
    print("Setting git remote and pushing code...")

    # Fix author identity
    run_git(["config", "user.name", "MXY66678"])
    run_git(["config", "user.email", f"{username}@users.noreply.github.com"])
    run_git(["commit", "--amend", "--reset-author", "--no-edit"])

    remote_url = f"https://{username}:{token}@github.com/{username}/{REPO_NAME}.git"
    result = run_git(["remote", "add", "origin", remote_url])
    if result.returncode != 0:
        run_git(["remote", "set-url", "origin", remote_url])

    result = run_git(["push", "-u", "origin", "main"])
    if result.returncode == 0:
        print(f"\nDone! https://github.com/{username}/{REPO_NAME}")
    else:
        print(f"Push failed: {result.stderr}")
        print("Trying: git push -u origin main --force")
        result = run_git(["push", "-u", "origin", "main", "--force"])
        if result.returncode == 0:
            print(f"\nDone! https://github.com/{username}/{REPO_NAME}")
        else:
            print(f"Still failed: {result.stderr}")


if __name__ == "__main__":
    main()
