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
import os
from utils import Commit

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
        # Read the commit hash stored in the branch file
        with open(branch_hash_path, "r") as f:
            commit_hash = f.read()

        # Construct path to the commit object (not currently used in logic)
        commit_hash_path = Path(".minigit") / "objects" / "commits" / commit_hash[:2] / commit_hash

        # Checkout the commit (this restores files and creates a detached HEAD)
        checkout_commit(commit_hash)

        # Re-attach HEAD to the branch reference instead of pointing directly to the commit
        # Format: "refs: refs/heads/branch_name" indicates HEAD points to a branch
        # This ensures future commits will update the branch pointer
        new_head = f"refs: refs/heads/{branch_name}"
        with open(".minigit/HEAD", "w") as f:
            f.write(new_head)
    else:
        # Branch doesn't exist, provide helpful error message
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
        branch_name (str): The name of the branch to delete, or None to default to current branch

    Note:
        This only deletes the branch reference, not the commits it pointed to.
    """

    # Check if HEAD is currently attached to this branch
    # head_tuple: (detached, branch_path, branch_name, branch_hash, commit_hash)
    head_tuple = utils.check_head()
    head_branch = head_tuple[2]  # Current branch name (if attached)
    head_detached = head_tuple[0]  # Boolean: True if HEAD is detached

    # Safety check: Only allow deletion if HEAD is not attached to this branch
    if (head_branch != branch_name) & (branch_name != None):
        # Safe to delete - either different branch or HEAD is detached
        branch_path = Path(".minigit") / "refs" / "heads" / branch_name
        os.remove(branch_path)
    elif (branch_name == None) & (head_detached):
        # Cannot default to current branch when HEAD is detached
        print("Cannot default to current branch because head is detached. Please try again.")
    else:
        # Trying to delete the current branch - not allowed
        print(f"Defaulting to current branch. Cannot delete {head_branch} branch because HEAD is currently attached to this branch.")


def branch_list():
    """
    List all branches in the repository.

    Displays each branch with its commit hash. If HEAD is attached to a branch,
    that branch is marked with an asterisk (*) to indicate it's the current branch.
    """
    subdir = Path(".minigit") / "refs" / "heads"

    # Get all branch files from .minigit/refs/heads/ directory
    files_path_objects = Path(".minigit/refs/heads").iterdir()  # Returns Path objects
    # Create dictionary of branch names to commit hashes
    # Dictionary comprehension extracts name and content from each file
    branch_files = {f.name: f.read_text() for f in files_path_objects if f.is_file()}

    # Check HEAD state to determine if we should mark the current branch
    head_tuple = utils.check_head()
    head_detached = head_tuple[0]  # Boolean: True if HEAD is detached

    if head_detached:
        # If HEAD is detached, no branch is current - just list all branches
        for k, v in branch_files.items():
            print(f"{v} {k}")
    else:
        # HEAD is attached to a branch - mark the current branch with asterisk
        dict_to_print = {}
        head_points_to = head_tuple[2]  # Name of current branch
        for k in branch_files.keys():
            if k == head_points_to:
                # Add asterisk prefix to current branch name
                dict_to_print[f"*{head_points_to}"] = branch_files[head_points_to]
            else:
                # Other branches remain unchanged
                dict_to_print[k] = branch_files[k]
        # Print all branches with current branch marked
        for k, v in dict_to_print.items():
            print(f"{v} {k}")
    
def merge(merge_branch_name, message):
    """
    Merge another branch into the current branch.

    Creates a merge commit with two parents and combines files from both branches.
    Files that changed in both branches are combined with a separator to indicate conflicts.

    Args:
        merge_branch_name (str): Name of the branch to merge into the current branch
        message (str): Commit message for the merge commit

    Strategy:
        - Unique files from either branch are included
        - Unchanged files are kept as-is
        - Files modified in both branches are concatenated with a separator (simple conflict resolution)
    """
    # Perspective of this function: I'm on branch A and bringing (merging) branch B into mine

    # Step 1: Get files from the current commit (the branch we're merging INTO)
    head_tuple = utils.check_head()
    current_commit_hash = head_tuple[4]  # Hash of current commit
    current_commit_object_path = Path(".minigit") / "objects" / "commits" / current_commit_hash[:2] / current_commit_hash
    with open(current_commit_object_path, "rb") as f:
        current_commit_object = pickle.load(f)
    current_commit_files = current_commit_object.files  # Dictionary {filename: hash}

    # Step 2: Get files from the merge branch (the branch we're merging FROM)
    merge_branch_path = Path(".minigit") / "refs" / "heads" / merge_branch_name
    with open(merge_branch_path, "r") as f:
        merge_branch_hash = f.read()  # Hash that merge branch points to
    merge_commit_object_path = Path(".minigit") / "objects" / "commits" / merge_branch_hash[:2] / merge_branch_hash
    with open(merge_commit_object_path, "rb") as f:
        merge_commit_object = pickle.load(f)
    merge_commit_files = merge_commit_object.files  # Dictionary {filename: hash}

    # Step 3: Categorize files into different merge scenarios

    # 3a. Files unique to one commit (exist in only one branch)
    unique_files_current_commit = {k: v for k, v in current_commit_files.items() if k not in merge_commit_files.keys()}
    unique_files_merge_commit = {k: v for k, v in merge_commit_files.items() if k not in current_commit_files.keys()}
    unique_files = unique_files_current_commit | unique_files_merge_commit  # Combine both sets

    # 3b. Files that exist in both commits
    files_in_both = {k: v for k, v in current_commit_files.items() if k in merge_commit_files.keys() and k in current_commit_files.keys()}

    # 3c. Files in both that have different hashes (modified in at least one branch)
    # Note: Both dictionaries will have the same keys, just different values (hashes)
    current_commit_changed_files = {k: v for k, v in files_in_both.items() if merge_commit_files[k] != current_commit_files[k]}
    merge_commit_changed_files = {k: v for k, v in files_in_both.items() if merge_commit_files[k] != current_commit_files[k]}

    # 3d. Files that are identical in both commits (no changes needed)
    unchanged_files = {k: v for k, v in files_in_both.items() if merge_commit_files[k] == current_commit_files[k]}

    # Step 4: Handle conflicting files (files changed in both branches)
    # Simple conflict resolution: concatenate both versions with a separator
    new_files = {}
    for k, v in current_commit_changed_files.items():
        # Get the blob (file content) from the current commit
        current_commit_blob_path = Path(".minigit") / "objects" / "blobs" / v[:2] / v
        merge_commit_hash = merge_commit_changed_files[k]  # Hash of same file in merge branch
        # Get the blob from the merge commit
        merge_commit_blob_path = Path(".minigit") / "objects" / "blobs" / merge_commit_hash[:2] / merge_commit_hash

        # Read both versions of the file
        with open(current_commit_blob_path, "rb") as f:
            current_commit_blob = f.read()

        with open(merge_commit_blob_path, "rb") as f:
            merge_commit_blob = f.read()

        # Combine both versions with a separator line (simple conflict marker)
        separator = b'\n==========================================================================\n'
        combined_files = current_commit_blob + separator + merge_commit_blob
        combined_files_hash = hashlib.sha1(combined_files).hexdigest()  # Hash the combined content
        new_files[k] = combined_files_hash  # Store mapping of filename to new hash

        # Store the combined blob in the objects database
        blob_subdir = Path(".minigit") / "objects" / "blobs" / combined_files_hash[:2]
        blob_subdir.mkdir(exist_ok=True)
        blob_path = blob_subdir / combined_files_hash
        with open(blob_path, "wb") as f:
            f.write(combined_files)

    # Step 5: Write merged files to working directory
    # Write the combined/conflicted files to working directory
    utils.write_files_from_dictionary(new_files)

    # Write unique files from merge branch to working directory
    utils.write_files_from_dictionary(unique_files_merge_commit)

    # Step 6: Create the merge commit object
    # Combine all file categories: unique files, unchanged files, and newly combined files
    all_files = unique_files | unchanged_files | new_files
    username = getpass.getuser()  # Get current user for author field

    # Create merge commit with TWO parents (current commit and merge branch commit)
    merge_commit = Commit(
        message = message,
        author = username,
        parent = [current_commit_hash, merge_branch_hash],  # Two parents indicate a merge
        files = all_files
    )

    # Step 7: Serialize, hash, and store the merge commit
    merge_commit_bytes = pickle.dumps(merge_commit)
    merge_commit_hash = hashlib.sha1(merge_commit_bytes).hexdigest()
    # Store commit in subdirectory using first 2 chars of hash
    merge_commit_subdir = Path(".minigit") / "objects" / "commits" / merge_commit_hash[:2]
    merge_commit_subdir.mkdir(exist_ok=True)
    merge_commit_path = Path(merge_commit_subdir) / merge_commit_hash
    with open(merge_commit_path, "wb") as f:
        f.write(merge_commit_bytes)

    # Step 8: Update HEAD to point to the new merge commit
    # Behavior depends on whether HEAD was detached or attached to a branch
    head_detached = head_tuple[0]

    if head_detached:
        # HEAD was detached: point HEAD directly to merge commit hash
        head_content = merge_commit_hash
        with open(".minigit/HEAD", "w") as f:
            f.write(head_content)
    else:
        # HEAD was attached to a branch: update the branch pointer to merge commit
        # This ensures the branch moves forward with the merge
        branch_name = head_tuple[2]
        branch_path = Path(".minigit") / "refs" / "heads" / branch_name
        with open(branch_path, "w") as f:
            f.write(merge_commit_hash)
        # Note: HEAD content stays the same (still pointing to the branch reference)

