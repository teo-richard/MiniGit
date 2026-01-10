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
from utils import Commit

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
    # Get dictionary of all files in working directory with their hashes
    # This has been refactored into a utility function to avoid code duplication
    directory_files = utils.get_directory_files_dictionary()


    # Load the staging area (index) to see what's been staged for next commit
    with open(".minigit/index", "rb") as f:
        staging_area = pickle.load(f)

    staging_area_additions = staging_area["additions"]  # dictionary {file name : hash}
    staging_area_removals = staging_area["removals"]  # list [file name, file name, ...]

    # Get HEAD information to find most recent commit
    # head_tuple contains: (detached, branch_path, branch_name, branch_hash, commit_hash)
    head_tuple = utils.check_head()
    prev_commit_hash = head_tuple[4]  # Hash of the most recent commit

    # Load the previous commit to see what files were tracked
    # Commits are stored in subdirectories using first 2 chars of hash for organization
    path_to_commit = Path(".minigit") / "objects" / "commits" / prev_commit_hash[:2] / prev_commit_hash
    with open(path_to_commit, "rb") as f:
        prev_commit_obj = pickle.load(f)
    prev_commit_files = prev_commit_obj.files  # Dictionary {filename: hash} of files in last commit

    # Categorize files by comparing working directory, staging area, and previous commit
    # This creates different file categories similar to `git status` output

    # Step 1: Get files that are tracked but not currently staged
    all_staged_files = list(staging_area["additions"].keys()) + staging_area["removals"]  # All files in the staging area
    not_staged = {k: v for k, v in directory_files.items() if k not in all_staged_files}  # Files in working dir but not staged
    tracked_not_staged = {k: v for k, v in not_staged.items() if k in prev_commit_files.keys()}  # Not staged but in previous commit

    # Step 2: Separate tracked-not-staged files into unmodified and modified
    # Compare current file hashes with hashes from the previous commit
    # All the k, v pairs in `tracked_not_staged.items()` come from your directory files
    unmodified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) == v}  # Hash unchanged
    modified_tracked_not_staged = {k: v for k, v in tracked_not_staged.items() if prev_commit_files.get(k) != v}  # Hash changed

    # Step 3: Find completely untracked files (never been committed or staged)
    not_tracked = {k: v for k, v in directory_files.items()
                    if k not in staging_area_additions  # Not staged for addition
                    and k not in staging_area_removals  # Not staged for removal
                    and k not in prev_commit_files}  # Not in previous commit

    # Display all categorized files with appropriate colors
    # Extract HEAD state information from the tuple
    head_detached = head_tuple[0]  # Boolean: True if HEAD is detached
    branch_name = head_tuple[2]  # Current branch name (if attached)

    # Display HEAD state
    if head_detached == True:
        print(f"\nNote: head is detached at {prev_commit_hash}.")
        print()
    else:
        print(f"\nHead attached to {branch_name} branch.")

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
    # Get current HEAD commit information
    head_tuple = utils.check_head()
    tip_hash = head_tuple[4]  # Hash of the most recent commit
    branch_name = head_tuple[2]  # Current branch name
    head_detached = head_tuple[0]  # Whether HEAD is detached

    # Load the most recent commit object
    # Commits are stored in subdirectories using first 2 chars of hash
    commit_path = Path(".minigit") / "objects" / "commits" / tip_hash[:2] / tip_hash
    with open(commit_path, "rb") as f:
        commit = pickle.load(f)

    # Display appropriate message based on HEAD state
    if head_detached:
        print(f"\nHead is detached. Log walks backwards from {tip_hash} to initial commit.\n")
    else:
        print(f"\nLog of all commits {branch_name} branch only!\n")

    # Handle case where there's only the initial commit (no parents)
    if commit.parent == []:
        print(f"There is only the initial commit.\n")
        print(f"Commit hash: {tip_hash}")
    else:
        # Print header for the most recent commit
        print("---------------------------\n")
        print(f"Commit hash: {tip_hash}")

    # Walk backwards through commit history following parent pointers
    # Continue until we reach the initial commit (which has no parent)
    while commit.parent != []:
        # Display commit details
        print(f"{commit.timestamp.strftime("%Y-%m-%d %H:%M:%S")} \n")
        print(f"Commit message: {commit.message}")
        print(f"Author: {commit.author}")
        print(f"Parent hash: {commit.parent}\n")

        # Display all files in this commit with their hashes
        print("Files:")
        for k, v in commit.files.items():
            print(f"{v} {k}")

        # Move to the parent commit (going backwards in history)
        next_commit_hash = commit.parent[0]  # Get hash of parent commit
        # Load the parent commit object from disk
        commit_path = Path(".minigit") / "objects" / "commits" / next_commit_hash[:2] / next_commit_hash
        with open(commit_path, "rb") as f:
            commit = pickle.load(f)

        # Print header for next commit in the log
        print("\n---------------------------\n")
        print(f"Commit hash: {next_commit_hash}")

    # Print the initial commit (has no parent, so wasn't printed in loop)
    print(f"{commit.timestamp.strftime("%Y-%m-%d %H:%M:%S")} \n")
    print(f"Commit message: {commit.message}")
    print(f"Author: {commit.author}")
    print(f"Parent hash: {commit.parent}\n")

    # Display files in initial commit
    print("Files:")
    for k, v in commit.files.items():
        print(f"{v} {k}")
    print("---------------------------\n")

    print("Log end.\n")


def amend(message):
    """
    Placeholder for amend command to modify the most recent commit.

    Not yet implemented. Would allow changing the message or contents
    of the most recent commit (similar to `git commit --amend`).
    """
    
    head_tuple = utils.check_head()
    hash = head_tuple[4] # Hash of most recent commit

    # Open the commit and get the object
    commit_subdir = Path(".minigit") / "objects" / "commits" / hash[:2] # Need the subdir path isolated for when checking subdir deletion
    commit_path = commit_subdir / hash
    with open(commit_path, "rb") as f:
        commit_object = pickle.load(f)

    # Change the message attribute to be the new message
    commit_object.message = message 

    # Delete the old commit spot (and the subdirectory if there's nothing left in it)
    commit_path.unlink()
    filelist = os.listdir(commit_subdir)
    if filelist:
        pass
    else:
        commit_subdir.rmdir()

    # Serialize and hash the updated commit object
    commit_bytes = pickle.dumps(commit_object)
    commit_hash = hashlib.sha1(commit_bytes).hexdigest()

    # Make a new spot in `/commits` for it
    new_commit_subdir = Path(".minigit") / "objects" / "commits" / commit_hash[:2]
    new_commit_subdir.mkdir(exist_ok=True)
    new_commit_path = new_commit_subdir / commit_hash
    with open(new_commit_path, "wb") as f:
        f.write(commit_bytes)

    # Update HEAD
    head_detached = head_tuple[0]
    branch_name = head_tuple[2]
    if head_detached:
        head_content = commit_hash
    else:
        head_content = f"refs: refs/heads{branch_name}"

    with open(".minigit/HEAD", "w") as f:
        f.write(head_content)
