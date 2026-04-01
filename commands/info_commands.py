"""
History and status commands for MiniGit.
Provides commands to view repository status and commit history.
"""

import pickle
from pathlib import Path
import hashlib
from datetime import datetime
import os
import utils
from utils import Commit
from utils import print_status
from collections import defaultdict




def collapse(all_tracked, not_tracked):
    all_tracked_file_parts_aggregated = set()
    for tracked_file in all_tracked:
        tracked_file_parts = tracked_file.split("/")
        all_tracked_file_parts_aggregated = all_tracked_file_parts_aggregated | set(tracked_file_parts)
    all_tracked_file_parts_aggregated = list(all_tracked_file_parts_aggregated)

    no_collapse = set()
    dirs = [] 
    for file in not_tracked:
        not_tracked_file_parts = file.split("/")
        if len(not_tracked_file_parts) == 1:
            no_collapse = no_collapse | set(not_tracked_file_parts)
        else:
            for i in range(0, len(not_tracked_file_parts)):
                if (not_tracked_file_parts[i] not in all_tracked_file_parts_aggregated):
                    file_to_add_to_dirs = ""
                    for part in range(0, i+1):
                        file_to_add_to_dirs = file_to_add_to_dirs + not_tracked_file_parts[part] + "/"
                    if file_to_add_to_dirs not in dirs:
                        dirs.append(file_to_add_to_dirs)
                else:
                    continue
                break

    no_collapse = list(no_collapse)
            
    return no_collapse, dirs


def status_general():
    _, staging_area_additions, staging_area_removals = utils.get_staging_area()

    if staging_area_additions:
        print_status(staging_area_additions,
                    "Files in staging area to be added to the next commit:",
                    "green")
    if staging_area_removals:
        print_status(staging_area_removals,
                    "Files in staging area to be removed in the next commit:",
                    "blue")
        
    status_files(staging_area_additions, staging_area_removals)

@utils.check_for_initial_commit
def status_files(staging_area_additions, staging_area_removals):
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
    directory_files = utils.get_directory_files_dictionary(".")


    head_tuple = utils.check_head()
    prev_commit_hash = head_tuple[4] # Hash of previous commit

    prev_commit_obj = utils.get_commit(prev_commit_hash)
    prev_commit_files = prev_commit_obj.files  # Dictionary {filename: hash} of files in last commit

    # Categorize files by comparing working directory, staging area, and previous commit
    # This creates different file categories similar to `git status` output

    # Step 1 and Step 2: 
    # 1. Get files that are tracked but not currently staged
    # 2. Separate tracked-not-staged files into unmodified and modified and compare current file hashes with hashes from the previous commit
    unmodified_tracked_not_staged, modified_tracked_not_staged = utils.get_unstaged_tracked_modified(
        directory_files, 
        staging_area_additions, 
        staging_area_removals,
        prev_commit_files)
    
    # Intermediate step: collect all tracked files (including those in the staging area):
    all_tracked = list(set(unmodified_tracked_not_staged.keys() | modified_tracked_not_staged.keys()) | set(staging_area_additions) | set(staging_area_removals))

    # Step 3: Find completely untracked files (never been committed or staged)
    not_tracked = {k: v for k, v in directory_files.items()
                    if k not in staging_area_additions  # Not staged for addition
                    and k not in staging_area_removals  # Not staged for removal
                    and k not in prev_commit_files}  # Not in previous commit
    
    # Collapse untracked files into their directories
    not_collapsed, collapsed_dirs = collapse(all_tracked, not_tracked.keys())
    not_tracked_updated = not_collapsed + collapsed_dirs


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


    if unmodified_tracked_not_staged or modified_tracked_not_staged or not_tracked_updated:
        if unmodified_tracked_not_staged:
            print_status(unmodified_tracked_not_staged,
                        "Tracked files not in staging area that have NOT been modified since last commit:",
                        "cyan")
        if modified_tracked_not_staged:
            print_status(modified_tracked_not_staged,
                        "Tracked files not in staging area that HAVE been modified since last commit:",
                        "yellow")
        if not_tracked_updated:
            print_status(not_tracked_updated,
                        "Files that are not tracked:",
                        "red")
        
        print("\nI hope you enjoyed this status update. I sure did!\n")
    else:
        print("There are NO STATUS UPDATES! GO DO SOMETHING WITH YOUR LIFE!!")

def display_commit_details(commit):
    print(f"{commit.timestamp.strftime("%Y-%m-%d %H:%M:%S")} \n")
    print(f"Commit message: {commit.message}")
    print(f"Author: {commit.author}")
    print(f"Parent hash: {commit.parent}\n")

    # Display all files in this commit with their hashes
    print("Files:")
    for k, v in commit.files.items():
        print(f"{v} {k}")


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
    commit = utils.get_commit(tip_hash)
    
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
        display_commit_details(commit)

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
    display_commit_details(commit)
    print("---------------------------\n")

    print("Log end.\n")

def log_all():
    ref_path = Path(".minigit/refs/heads")

    unique_commit_hashes = {}

    for branch in os.listdir(ref_path):
        branch_path = os.path.join(ref_path, branch)
        with open(branch_path, "r") as f:
            commit_hash = f.read()

        commit = utils.get_commit(commit_hash)

        while commit.parent != []:
            if commit_hash not in unique_commit_hashes: # Is the hash of the commit in this iteration in unique_commit_hashes?
                unique_commit_hashes[commit_hash] = commit.timestamp # If not, add to dictionary
            
            commit_hash = commit.parent[0] # Getting the hash of the commit for our next iteration in the loop
            commit = utils.get_commit(commit_hash) # Getting the commit object
        
        # and put the initial commit in unique_commit_hashes
        if commit_hash not in unique_commit_hashes:
            unique_commit_hashes[commit_hash] = commit.timestamp

    sorted_unique_commit_hashes = dict(sorted(unique_commit_hashes.items(), key = lambda x: (x[1] is None, x[1]), reverse=True))

    print("---------------------------")
    for commit_hash in sorted_unique_commit_hashes.keys():
        commit_obj = utils.get_commit(commit_hash)
        display_commit_details(commit_obj)
    print("---------------------------")






def reflog():
    commits_dir = Path(".minigit/objects/commits")
    hashes = {}
    for prefix in os.listdir(commits_dir):
        prefix_path = os.path.join(commits_dir, prefix) # Path to folder containing commit objects starting with some prefix
        for filename in os.listdir(prefix_path):
            commit_path = os.path.join(prefix_path, filename)
            with open(commit_path, "rb") as f:
                commit_obj = pickle.load(f)
            commit_timestamp = commit_obj.timestamp
            hashes[filename] = commit_timestamp

    sorted_hashes = dict(sorted(hashes.items(), key = lambda x: (x[1] is None, x[1]), reverse=True))
    
    print("---------------------------")

    for commit_hash in sorted_hashes:
        commit_path = Path(f".minigit/objects/commits/{commit_hash[0:2]}/{commit_hash}")
        with open(commit_path, "rb") as f:
            commit_obj = pickle.load(f)

        print(f"Commit hash: {commit_hash}")
        display_commit_details(commit_obj)
        print("---------------------------")

        

def amend(message):
    """
    Placeholder for amend command to modify the most recent commit.

    Not yet implemented. Would allow changing the message or contents
    of the most recent commit (similar to `git commit --amend`).
    """
    
    head_tuple = utils.check_head()
    recent_commit_hash = head_tuple[4] # Hash of most recent commit

    # Open the commit and get the object
    commit_subdir = Path(".minigit") / "objects" / "commits" / recent_commit_hash[:2] # Need the subdir path isolated for when checking subdir deletion
    commit_path = commit_subdir / recent_commit_hash
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
        head_content = f"refs: refs/heads/{branch_name}"
        # update branch tip
        with open(f".minigit/refs/heads/{branch_name}", "w") as f:
            f.write(commit_hash)

    # update HEAD
    with open(".minigit/HEAD", "w") as f:
        f.write(head_content)


