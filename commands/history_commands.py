"""
History and status commands for MiniGit.
Provides commands to view repository status and commit history.
"""

import pickle
from pathlib import Path
import hashlib
from datetime import datetime
import os
from colorama import Fore, Style, init
from typing import List
import utils

def print_status(filelist: dict | list, message:str, color:str) -> bool:
    """
    Print a formatted list of files with color coding.

    Args:
        filelist: Either a dictionary {filename: hash} or list of filenames
        message: Header message to display before the file list
        color: Color name for the output (red, green, yellow, blue, magenta, cyan, white)

    Returns:
        bool: Always returns True (currently unused)
    """
    # Map color names to colorama color codes
    colors = {
        "red": Fore.RED,
        "green": Fore.GREEN,
        "yellow": Fore.YELLOW,
        "blue": Fore.BLUE,
        "magenta": Fore.MAGENTA,
        "cyan": Fore.CYAN,
        "white": Fore.WHITE,
        "yellow": Fore.LIGHTYELLOW_EX
    }
    color_code = colors[color]
    print("\n" + message)

    # Handle list vs dictionary input
    if isinstance(filelist, List):
        # For lists, print just the filename
        for item in filelist:
            print(f"{color_code} {item}{Style.RESET_ALL}")
    else:
        # For dictionaries, print hash and filename
        for key, value in filelist.items():
            print(f"{color_code} {value} {key}{Style.RESET_ALL}")


def check_ignore(filepath):
    """
    Check if a file path should be ignored by MiniGit.

    Ignores:
    - Python cache files (__pycache__, .pyc)
    - Virtual environments (venv/)
    - Git repositories (.git, .minigit)
    - System files (.DS_Store)
    - Hidden files/directories (starting with .)

    Args:
        filepath: Path to check

    Returns:
        bool: True if file should be ignored, False otherwise
    """
    # List of patterns to ignore
    ignore_patterns = [
        '__pycache__',
        '.pyc',
        'venv/',
        '.git',
        '.minigit',
        '.DS_Store',
    ]

    # Check if any ignore pattern is in the filepath
    for pattern in ignore_patterns:
        if pattern in filepath:
            return True

    # Also ignore any hidden files/directories (starting with .)
    parts = filepath.split(os.sep)
    if any(part.startswith(".") and part != "." for part in parts):
        return True

    return False


def status():
    """
    Display the current repository status.

    Shows:
    1. HEAD state (attached to branch or detached)
    2. Files staged for addition
    3. Files staged for removal
    4. Tracked files not staged (unmodified)
    5. Tracked files not staged (modified)
    6. Untracked files

    This function compares:
    - Working directory files
    - Staging area (index)
    - Previous commit files
    to categorize all files appropriately.
    """
    directory_files = {}

    # Walk through all files in the working directory and compute their hashes
    # `dirs` is os.walk's internal list of dirs it will walk to in the starting folder
    for root, dirs, files in os.walk("."):
        for file in files:
            # Filter out directories that should be ignored
            dirs[:] = [d for d in dirs if not check_ignore(d)]
            filepath = os.path.join(root, file)
            # Skip individual files that should be ignored
            if check_ignore(filepath) == True:
                continue
            # Read file and compute SHA-1 hash
            with open(filepath, "rb") as f:
                file_byte = f.read()

            file_hash = hashlib.sha1(file_byte).hexdigest()
            # Normalize path to remove leading './' and use forward slashes
            normalized_path = filepath.lstrip("./").replace("\\", "/")
            directory_files[normalized_path] = file_hash


    # Load the staging area to see what's been staged
    with open(".minigit/index", "rb") as f:
        staging_area = pickle.load(f)

    staging_area_additions = staging_area["additions"]  # dictionary {file name : hash}
    staging_area_removals = staging_area["removals"]  # list [file name, file name, ...]

    # Get HEAD information to find current commit
    head_tuple = utils.check_head()
    prev_commit_hash = head_tuple[4]

    # Load the previous commit to see what files were tracked
    path_to_commit = Path(".minigit") / "objects" / "commits" / prev_commit_hash[:2] / prev_commit_hash
    with open(path_to_commit, "rb") as f:
        prev_commit_obj = pickle.load(f)
    prev_commit_files = prev_commit_obj.files  # Dictionary of files in last commit

    # Categorize files by comparing working directory, staging area, and previous commit

    # Get files that are tracked but not currently staged
    all_staged_files = list(staging_area["additions"].keys()) + staging_area["removals"]
    not_staged = {k: v for k, v in directory_files.items() if k not in all_staged_files}
    tracked_not_staged = {k: v for k, v in not_staged.items() if k in prev_commit_files.keys()}

    # Separate tracked-not-staged files into unmodified and modified
    unmodified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) == v}
    modified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) != v}

    # Find completely untracked files (not in staging area or previous commit)
    not_tracked = {k: v for k, v in directory_files.items()
                    if k not in staging_area_additions
                    and k not in staging_area_removals
                    and k not in prev_commit_files}

    # Display all categorized files with appropriate colors
    head_detached = head_tuple[0]
    branch_name = head_tuple[2]
    if head_detached == True:
        print(f"Note: head is detached at {prev_commit_hash}.")
        print()
    else:
        print(f"Head attached to {branch_name} branch.")

    print_status(staging_area["additions"],
                 "Files in staging area to be added to the next commit:",
                 "green")

    print_status(staging_area["removals"],
                 "Files in staging area to be removed in the next commit:",
                 "blue")

    print_status(unmodified_tracked_not_staged,
                 "Tracked files not in staging area that have NOT been modified since last commit:",
                 "cyan")

    print_status(modified_tracked_not_staged,
                 "Tracked files not in staging area that HAVE been modified since last commit:",
                 "yellow")

    print_status(not_tracked,
                 "Files that are not tracked:",
                 "red")

    print("\nI hope you enjoyed this status update. I sure did!\n")



def log():
    """
    Display the commit history for the current branch.

    Shows all commits from HEAD back to the initial commit, including:
    - Commit hash
    - Timestamp
    - Commit message
    - Author
    - Parent commit hash
    - Files included in each commit

    Walks backwards through the commit chain by following parent pointers.
    """
    # Get current HEAD commit
    head_tuple = utils.check_head()
    tip_hash = head_tuple[4]

    # Load the most recent commit
    commit_path = Path(".minigit") / "objects" / "commits" / tip_hash[:2] / tip_hash
    with open(commit_path, "rb") as f:
        commit = pickle.load(f)

    print("Log of all commits IN THIS BRANCH ONLY\n")

    # Handle case where there's only the initial commit
    if commit.parent == None:
        print(f"There is only the initial commit.")
        print(f"Commit hash: {tip_hash}")
    else:
        # Print header for the most recent commit
        print("---------------------------\n")
        print(f"Commit hash: {tip_hash}")

    # Walk backwards through commit history following parent pointers
    while commit.parent != None:
        print(f"{commit.timestamp.strftime("%Y-%m-%d %H:%M:%S")} \n")
        print(f"Commit message: {commit.message}")
        print(f"Author: {commit.author}")
        print(f"Parent hash: {commit.parent}\n")

        print("Files:")
        for k, v in commit.files.items():
            print(f"{v} {k}")

        next_commit_hash = commit.parent # This commit's parent hash is the hash of the next commit we'll list in the log
        # Load the parent commit
        commit_path = Path(".minigit") / "objects" / "commits" / commit.parent[:2] / commit.parent
        with open(commit_path, "rb") as f:
            commit = pickle.load(f)

        # Print header for next commit
        print("\n---------------------------\n")
        print(f"Commit hash: {next_commit_hash}")

    # Print the initial commit (has no parent)
    print(f"{commit.timestamp.strftime("%Y-%m-%d %H:%M:%S")} \n")
    print(f"Commit message: {commit.message}")
    print(f"Author: {commit.author}")
    print(f"Parent hash: {commit.parent}\n")

    print("Files:")
    for k, v in commit.files.items():
        print(f"{v} {k}")
    print("---------------------------\n")

    print("Log end.\n")
