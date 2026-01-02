"""
Branch management commands for MiniGit.
This module handles branch creation, deletion, switching, and commit checkout operations.
"""

from pathlib import Path
import datetime
import pickle
import hashlib
import getpass
import utils
import _osx_support
import os

def checkout_commit(checkout_hash):
    """
    Checkout a specific commit by its hash, creating a detached HEAD state.

    This function:
    1. Loads the commit object from storage
    2. Restores all files from that commit to the working directory
    3. Updates HEAD to point directly to the commit (detached state)

    Args:
        checkout_hash (str): The hash of the commit to checkout

    Note:
        For branch checkout, use branch_switch() instead to maintain an attached HEAD.
    """
    # Load the commit object from the objects database
    # Commits are stored in subdirectories named by first 2 chars of hash
    commit_path = Path(".minigit") / "objects" / "commits" / checkout_hash[:2] / checkout_hash

    with open(commit_path, "rb") as f:
        commit_object = pickle.load(f)

    # Extract the file mappings (filename -> blob hash) from the commit
    commit_files = commit_object.files

    # Restore all files from the commit to the working directory
    for filename, hash in commit_files.items():
        # Retrieve the blob (file content) from the objects database
        blob_path = Path(".minigit") / "objects" / "blobs" / hash[:2] / hash
        with open(blob_path, "rb") as f:
            blob = f.read()  # Read the file content in binary form

        # Overwrite the working directory file with the content from the blob
        with open(filename, "wb") as f:
            f.write(blob)

    # Update HEAD to point directly to the commit hash (detached HEAD state)
    # This means HEAD is not attached to any branch
    with open(".minigit/HEAD", "w") as f:
        f.write(checkout_hash)


def branch_switch(branch_name):
    """
    Switch to an existing branch, updating HEAD to be attached to that branch.

    This function:
    1. Reads the commit hash that the branch points to
    2. Checks out that commit (temporarily creating a detached HEAD)
    3. Re-attaches HEAD to the branch reference

    Args:
        branch_name (str): The name of the branch to switch to
    """
    # Read the commit hash that this branch currently points to
    branch_hash_path = Path(".minigit") / "refs" / "heads" / branch_name
    if branch_hash_path.exists():
        with open(branch_hash_path, "r") as f:
            commit_hash = f.read()

        commit_hash_path = Path(".minigit") / "objects" / "commits" / commit_hash[:2] / commit_hash

        # Checkout the commit (this creates a detached HEAD)
        checkout_commit(commit_hash)

        # Attach HEAD to the branch reference instead of pointing directly to the commit
        # This ensures future commits will update the branch pointer
        new_head = f"refs: refs/heads/{branch_name}"
        with open(".minigit/HEAD", "w") as f:
            f.write(new_head)
    else:
        print(f"The {branch_name} branch does not seem to exist. Use switch -c {branch_name} to create it.")

def branch_create(branch_name):
    """
    Create a new branch at the current commit and switch to it.

    This function:
    1. Creates a new branch reference file pointing to the current commit
    2. Updates HEAD to be attached to the new branch

    Args:
        branch_name (str): The name of the new branch to create
    """
    # Determine the path for the new branch reference file
    new_branch_path = Path(".minigit") / "refs" / "heads" / branch_name

    # Get the current commit hash that HEAD is pointing to
    head_tuple = utils.check_head()
    current_commit_hash = head_tuple[4]

    # Create the branch file containing the current commit hash
    # The branch now points to the same commit as HEAD
    with open(new_branch_path, "w") as f:
        f.write(current_commit_hash)

    # Attach HEAD to the newly created branch
    # Future commits will now update this branch pointer
    new_head = f"refs: refs/heads/{branch_name}"
    with open(".minigit/HEAD", "w") as f:
        f.write(new_head)
    

def branch_delete(branch_name):
    """
    Delete a branch by removing its reference file.

    This function prevents deletion if HEAD is currently attached to the branch
    (similar to Git's safety check to prevent deleting the current branch).

    Args:
        branch_name (str): The name of the branch to delete

    Note:
        This only deletes the branch reference, not the commits it pointed to.
    """
    # Check if HEAD is currently attached to this branch
    head_tuple = utils.check_head()
    head_branch = head_tuple[2]

    # Only allow deletion if HEAD is not attached to this branch
    if head_branch != branch_name:
        branch_path = Path(".minigit") / "refs" / "heads" / branch_name
        os.remove(branch_path)
    else:
        print(f"Cannot delete {branch_name} branch because HEAD is attached to this branch.")


def branch_list():
    """
    List all branches in the repository.

    TODO: Implementation incomplete
    - Should walk through .minigit/refs/heads/ directory
    - Display branch names and their commit hashes
    - Mark the current branch with an indicator (e.g., asterisk)
    """
    subdir = Path(".minigit") / "refs" / "heads"
    # Use os.walk to get the files then just list the names and the hashes
    # TODO: Complete this implementation

