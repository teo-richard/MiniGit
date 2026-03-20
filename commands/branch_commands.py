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
from utils import CommitNotFoundError
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

    # Get the files currently being tracked
    tracked_files = utils.get_tracked_files()

    # Check if the files have been modified
    checkout_good = True
    for file, hash in tracked_files.items():
        if not os.path.exists(file):
            print(f"Unable to checkout: tracked file {file} is missing. Did you delete it?")
            checkout_good = False
            break
        try:
            with open(file, "rb") as f:
                filecontent = f.read()
            filehash = hashlib.sha1(filecontent).hexdigest()
            if filehash != hash:
                print("Unable to checkout because it will overwrite changes that have not been committed. ")
                checkout_good = False
                break
        except (PermissionError, IOError, IsADirectoryError) as e:
            print(f"Unable to checkout: There is a problem reading {file}.\n{e}")
            checkout_good = False
            break

    if checkout_good == True:
        utils.get_old_commit_state(checkout_hash, tracked_files)
        
        # Update HEAD to point directly to the commit hash (detached HEAD state)
        # This means HEAD is not attached to any branch
        with open(".minigit/HEAD", "w") as f:
            f.write(checkout_hash)

        print("\nWARNING. You are in a DETACHED head state." \
            "To create a new branch, use 'minigit switch -c <branch_name>'." \
            "\nThen, you may commit new changes with 'minigit commit -m <commite message>'." \
            "\nOr, to get back to an existing branch, use 'minigit switch <branch name>'.")


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
    

def remove_branch_ref(branch_name):
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


def branch_delete(user_input):
    for branch in user_input:
        remove_branch_ref(branch)








    
def merge(merge_branch_name, message):
    """
    Merge another branch into the current branch.

    First checks if a fast-forward is possible (local is strictly behind the merge
    branch). If so, just moves the branch pointer — no merge commit needed. Otherwise,
    performs a three-way merge using the common ancestor.

    Args:
        merge_branch_name (str): Name of the branch to merge into the current branch.
        message (str): Commit message for the merge commit (three-way merge only).

    Three-Way Merge Strategy:
        - Files unique to either branch: included as-is
        - Files unchanged in both branches: kept as-is
        - Files changed in only one branch: keep the changed version
        - Files changed in both branches: concatenate with a conflict separator
    """
    # ============================================================================
    # STEP 1: Load commit objects for both branches
    # ============================================================================
    head_tuple = utils.check_head()
    branch_name = head_tuple[2]
    head_detached = head_tuple[0]

    # Current branch — the branch we're merging INTO
    current_commit_hash = head_tuple[4]
    current_commit_object_path = Path(".minigit") / "objects" / "commits" / current_commit_hash[:2] / current_commit_hash
    with open(current_commit_object_path, "rb") as f:
        current_commit_object = pickle.load(f)
    current_commit_files = current_commit_object.files  # {filename: blob_hash}

    # Merge branch — the branch we're merging FROM
    merge_branch_path = Path(".minigit") / "refs" / "heads" / merge_branch_name
    with open(merge_branch_path, "r") as f:
        merge_branch_tip_hash = f.read()
    merge_branch_commit_object = utils.get_commit(merge_branch_tip_hash)
    merge_branch_commit_files = merge_branch_commit_object.files  # {filename: blob_hash}

    # Already up to date — both tips point to the same commit
    if current_commit_hash == merge_branch_tip_hash:
        return "Already up to date."

    # ============================================================================
    # STEP 2: Find common ancestor and check for fast-forward
    # ============================================================================

    # The common ancestor is the point where the two branches last diverged
    ancestor, ancestor_hash = utils.find_common_ancestor(current_commit_object, current_commit_hash, merge_branch_commit_object)

    # Fast-forward: our current commit IS the common ancestor, meaning we haven't
    # made any commits that the merge branch doesn't already have. Just move the
    # branch pointer forward — no merge commit needed.
    if current_commit_hash == ancestor_hash:
        if head_detached:
            with open(".minigit/HEAD", "w") as f:
                f.write(merge_branch_tip_hash)
        else:
            branch_path = Path(".minigit") / "refs" / "heads" / branch_name
            with open(branch_path, "w") as f:
                f.write(merge_branch_tip_hash)
        utils.make_blob_current(merge_branch_commit_files)
        return

    ancestor_files = ancestor.files  # {filename: blob_hash}

    # ============================================================================
    # STEP 3: Categorize files across both branches
    # ============================================================================

    # Files that only exist in one branch — include them directly
    unique_files_current_commit = {k: v for k, v in current_commit_files.items()
                                   if k not in merge_branch_commit_files.keys()}
    unique_files_merge_commit = {k: v for k, v in merge_branch_commit_files.items()
                                 if k not in current_commit_files.keys()}
    unique_files = unique_files_current_commit | unique_files_merge_commit

    # Files that exist in both branches but differ — modified in at least one branch
    current_commit_changed_files = {k: v for k, v in current_commit_files.items()
                                    if k in merge_branch_commit_files.keys()
                                    and merge_branch_commit_files[k] != current_commit_files[k]}
    merge_commit_changed_files = {k: v for k, v in merge_branch_commit_files.items()
                                  if k in current_commit_files.keys()
                                  and merge_branch_commit_files[k] != current_commit_files[k]}

    # ============================================================================
    # STEP 4: Three-way merge — decide which version of each changed file to keep
    # ============================================================================

    # Changed only in the current branch (merge branch matches ancestor) — keep current
    current_commit_keep_change = {k: v for k, v in current_commit_changed_files.items()
                                  if k in ancestor_files.keys()
                                  and current_commit_changed_files[k] != ancestor_files[k]
                                  and merge_commit_changed_files[k] == ancestor_files[k]}

    # Changed only in the merge branch (current branch matches ancestor) — keep merge
    merge_commit_keep_change = {k: v for k, v in merge_commit_changed_files.items()
                                  if k in ancestor_files.keys()
                                  and merge_commit_changed_files[k] != ancestor_files[k]
                                  and current_commit_changed_files[k] == ancestor_files[k]}

    # Changed in BOTH branches — conflict, concatenate both versions with a separator
    changed_files_cc = {k: v for k, v in current_commit_changed_files.items()
                        if k not in current_commit_keep_change and k not in merge_commit_keep_change}
    changed_files_mc = {k: v for k, v in merge_commit_changed_files.items()
                        if k not in merge_commit_keep_change and k not in current_commit_keep_change}

    # Files identical in both branches — no action needed, keep as-is
    files_in_both = {k: v for k, v in current_commit_files.items()
                     if k in merge_branch_commit_files.keys() and k in current_commit_files.keys()}
    unchanged_files = {k: v for k, v in files_in_both.items()
                       if merge_branch_commit_files[k] == current_commit_files[k]}

    # ============================================================================
    # STEP 5: Apply changes to the working directory
    # ============================================================================

    # Write non-conflicted changes to disk
    utils.make_blob_current(current_commit_keep_change)
    utils.make_blob_current(merge_commit_keep_change)

    # Resolve conflicts by concatenating both versions with a separator
    new_files = {}  # {filename: new_blob_hash} for conflict-resolved files
    for k, v in changed_files_cc.items():
        current_commit_blob_path = Path(".minigit") / "objects" / "blobs" / v[:2] / v
        with open(current_commit_blob_path, "rb") as f:
            current_commit_blob = f.read()

        # Both dicts have the same keys after conflict filtering
        merge_conflict_blob_hash = changed_files_mc[k]
        merge_commit_blob_path = Path(".minigit") / "objects" / "blobs" / merge_conflict_blob_hash[:2] / merge_conflict_blob_hash
        with open(merge_commit_blob_path, "rb") as f:
            merge_commit_blob = f.read()

        separator = b'\n==========================================================================\n'
        combined_files = current_commit_blob + separator + merge_commit_blob
        combined_files_hash = hashlib.sha1(combined_files).hexdigest()
        new_files[k] = combined_files_hash

        # Store the combined blob in the objects database
        blob_subdir = Path(".minigit") / "objects" / "blobs" / combined_files_hash[:2]
        blob_subdir.mkdir(exist_ok=True)
        blob_path = blob_subdir / combined_files_hash
        with open(blob_path, "wb") as f:
            f.write(combined_files)

    utils.write_files_from_dictionary(new_files)
    utils.write_files_from_dictionary(unique_files_merge_commit)

    # ============================================================================
    # STEP 6: Create and store the merge commit
    # ============================================================================

    # Final file state = all categorized files combined
    all_files = unique_files | unchanged_files | new_files | current_commit_keep_change | merge_commit_keep_change
    username = getpass.getuser()

    # A merge commit has two parents, distinguishing it from a regular commit
    merge_commit = Commit(
        message = message,
        author = username,
        parent = [current_commit_hash, merge_branch_tip_hash],
        files = all_files
    )

    merge_commit_bytes = pickle.dumps(merge_commit)
    merge_commit_hash = hashlib.sha1(merge_commit_bytes).hexdigest()
    merge_commit_subdir = Path(".minigit") / "objects" / "commits" / merge_commit_hash[:2]
    merge_commit_subdir.mkdir(exist_ok=True)
    merge_commit_path = Path(merge_commit_subdir) / merge_commit_hash
    with open(merge_commit_path, "wb") as f:
        f.write(merge_commit_bytes)

    # ============================================================================
    # STEP 7: Advance HEAD or the current branch pointer to the merge commit
    # ============================================================================

    if head_detached:
        # Detached HEAD: point HEAD directly at the new merge commit
        with open(".minigit/HEAD", "w") as f:
            f.write(merge_commit_hash)
    else:
        # Attached HEAD: update the branch pointer; HEAD itself stays as-is
        branch_path = Path(".minigit") / "refs" / "heads" / branch_name
        with open(branch_path, "w") as f:
            f.write(merge_commit_hash)

