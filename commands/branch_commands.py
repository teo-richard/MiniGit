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
        try:
            utils.get_old_commit_state(checkout_hash, tracked_files)
            
            # Update HEAD to point directly to the commit hash (detached HEAD state)
            # This means HEAD is not attached to any branch
            with open(".minigit/HEAD", "w") as f:
                f.write(checkout_hash)
        except CommitNotFoundError as e:
            print(e)


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


def find_common_ancestor(commit1, commit2):
    """
    Find the most recent common ancestor of two commits using BFS.

    This is used during merge operations to implement three-way merge.
    The common ancestor is the point where two branches diverged.

    Args:
        commit1: First Commit object (typically the current branch tip)
        commit2: Second Commit object (typically the merge branch tip)

    Returns:
        Commit: The common ancestor Commit object
    """
    # Set to track all ancestors of commit1
    commit1_ancestors = set()

    # BFS queue starting from commit1's parent
    queue = [commit1.parent[0]]

    # Collect all ancestors of commit1 by walking backwards through history
    while queue:
        current = queue.pop(0)
        if current in commit1_ancestors:
            continue
        commit1_ancestors.add(current)
        next_commit_path = Path(".minigit") / "objects" / "commits" / current[:2] / current
        with open(next_commit_path, "rb") as f:
            next_commit_object = pickle.load(f)

        if next_commit_object.parent:
            next_commit_parent = next_commit_object.parent[0]
            queue.append(next_commit_parent)
        else:
            break

    # Walk backwards from commit2 to find the first hash that exists in commit1's ancestors
    # The first match is the most recent common ancestor
    queue = [commit2.parent[0]]
    while queue:
        current = queue.pop(0)
        if current in commit1_ancestors:
                ancestor_hash = current
                ancestor_path = Path(".minigit") / "objects" / "commits" / ancestor_hash[:2] / ancestor_hash
                with open(ancestor_path, "rb") as f:
                    ancestor = pickle.load(f)
                return ancestor
        
        next_commit_path = Path(".minigit") / "objects" / "commits" / current[:2] / current
        with open(next_commit_path, "rb") as f:
            next_commit_object = pickle.load(f)
        
        next_commit_parent = next_commit_object.parent[0]
        queue.append(next_commit_parent)
    





    
def merge(merge_branch_name, message):
    """
    Merge another branch into the current branch using a three-way merge strategy.

    This implements a three-way merge that:
    1. Finds the common ancestor between the two branches
    2. Categorizes files based on how they changed relative to the ancestor
    3. Creates a merge commit with two parents combining files from both branches
    4. Handles conflicts by concatenating both versions with a separator

    Args:
        merge_branch_name (str): Name of the branch to merge into the current branch
        message (str): Commit message for the merge commit

    Merge Strategy (Three-Way):
        - Files unique to either branch: Included in merge result
        - Files unchanged in both branches: Keep as-is from ancestor
        - Files changed in only one branch: Keep the changed version
        - Files changed in both branches: Concatenate with separator (conflict marker)

    File Categories:
        - unique_files: Files that exist in only one branch
        - unchanged_files: Files identical in both branches
        - current_commit_keep_change: Changed only in current branch
        - merge_commit_keep_change: Changed only in merge branch
        - changed_files_cc/mc: Changed in BOTH branches (conflicts)
    """
    # ============================================================================
    # STEP 1: Load commit objects from current branch and merge branch
    # ============================================================================

    # Get the current commit (the branch we're merging INTO)
    head_tuple = utils.check_head()
    current_commit_hash = head_tuple[4]
    current_commit_object_path = Path(".minigit") / "objects" / "commits" / current_commit_hash[:2] / current_commit_hash
    with open(current_commit_object_path, "rb") as f:
        current_commit_object = pickle.load(f)
    current_commit_files = current_commit_object.files  # {filename: blob_hash}

    # Get the merge branch commit (the branch we're merging FROM)
    merge_branch_path = Path(".minigit") / "refs" / "heads" / merge_branch_name
    with open(merge_branch_path, "r") as f:
        merge_branch_hash = f.read()
    merge_commit_object = utils.get_commit(merge_branch_hash)
    merge_commit_files = merge_commit_object.files  # {filename: blob_hash}

    # Find the common ancestor commit for three-way merge
    ancestor = find_common_ancestor(current_commit_object, merge_commit_object)
    ancestor_files = ancestor.files  # {filename: blob_hash}

    # ============================================================================
    # STEP 2: Categorize files based on presence in each commit
    # ============================================================================

    # Files that exist in only one of the two branches (not in both)
    # These are straightforward - just include them in the merge
    unique_files_current_commit = {k: v for k, v in current_commit_files.items()
                                   if k not in merge_commit_files.keys()}
    unique_files_merge_commit = {k: v for k, v in merge_commit_files.items()
                                 if k not in current_commit_files.keys()}
    unique_files = unique_files_current_commit | unique_files_merge_commit

    # Files that exist in BOTH branches but have different blob hashes
    # These files were modified in at least one branch since they diverged
    current_commit_changed_files = {k: v for k, v in current_commit_files.items()
                                    if k in merge_commit_files.keys()
                                    and merge_commit_files[k] != current_commit_files[k]}
    merge_commit_changed_files = {k: v for k, v in merge_commit_files.items()
                                  if k in current_commit_files.keys()
                                  and merge_commit_files[k] != current_commit_files[k]}

    # ============================================================================
    # STEP 3: Use three-way merge to determine which changes to keep
    # ============================================================================

    # Files changed in ONLY the current branch (not in merge branch)
    # Keep these changes: file differs from ancestor in current branch only
    # Condition: current != ancestor AND merge == ancestor
    current_commit_keep_change = {k: v for k, v in current_commit_changed_files.items()
                                  if k in ancestor_files.keys()
                                  and current_commit_changed_files[k] != ancestor_files[k]
                                  and merge_commit_changed_files[k] == ancestor_files[k]}

    # Files changed in ONLY the merge branch (not in current branch)
    # Keep these changes: file differs from ancestor in merge branch only
    # Condition: merge != ancestor AND current == ancestor
    merge_commit_keep_change = {k: v for k, v in merge_commit_changed_files.items()
                                  if k in ancestor_files.keys()
                                  and merge_commit_changed_files[k] != ancestor_files[k]
                                  and current_commit_changed_files[k] == ancestor_files[k]}

    # Files changed in BOTH branches (conflicts)
    # These need special handling - we'll concatenate both versions
    # Filter out files that were only changed in one branch
    # Both dictionaries will have matching keys after this filtering
    changed_files_cc = {k: v for k, v in current_commit_changed_files.items()
                        if k not in current_commit_keep_change and k not in merge_commit_keep_change}
    changed_files_mc = {k: v for k, v in merge_commit_changed_files.items()
                        if k not in merge_commit_keep_change and k not in current_commit_keep_change}

    # Files that exist in both branches with identical content (no conflict)
    files_in_both = {k: v for k, v in current_commit_files.items()
                     if k in merge_commit_files.keys() and k in current_commit_files.keys()}
    unchanged_files = {k: v for k, v in files_in_both.items()
                       if merge_commit_files[k] == current_commit_files[k]}

    # ============================================================================
    # STEP 4: Apply changes to working directory
    # ============================================================================

    # Write files that changed in only one branch to the working directory
    utils.make_blob_current(current_commit_keep_change)
    utils.make_blob_current(merge_commit_keep_change)

    # Handle conflicting files (changed in both branches)
    # Strategy: Concatenate both versions with a separator line
    new_files = {}  # Will store {filename: new_blob_hash} for conflicted files
    for k, v in changed_files_cc.items():
        # Load the blob content from current branch
        current_commit_blob_path = Path(".minigit") / "objects" / "blobs" / v[:2] / v
        with open(current_commit_blob_path, "rb") as f:
            current_commit_blob = f.read()

        # Load the blob content from merge branch
        merge_commit_hash = changed_files_mc[k]  # Safe because both dicts have same keys
        merge_commit_blob_path = Path(".minigit") / "objects" / "blobs" / merge_commit_hash[:2] / merge_commit_hash
        with open(merge_commit_blob_path, "rb") as f:
            merge_commit_blob = f.read()

        # Combine both versions with a conflict separator
        separator = b'\n==========================================================================\n'
        combined_files = current_commit_blob + separator + merge_commit_blob
        combined_files_hash = hashlib.sha1(combined_files).hexdigest()
        new_files[k] = combined_files_hash

        # Store the combined content as a new blob in the objects database
        blob_subdir = Path(".minigit") / "objects" / "blobs" / combined_files_hash[:2]
        blob_subdir.mkdir(exist_ok=True)
        blob_path = blob_subdir / combined_files_hash
        with open(blob_path, "wb") as f:
            f.write(combined_files)

    # Write conflicted files and unique files from merge branch to working directory
    utils.write_files_from_dictionary(new_files)
    utils.write_files_from_dictionary(unique_files_merge_commit)

    # ============================================================================
    # STEP 5: Create and store the merge commit
    # ============================================================================

    # Combine all file categories to create the final state after merge
    all_files = unique_files | unchanged_files | new_files | current_commit_keep_change | merge_commit_keep_change
    username = getpass.getuser()

    # Create a merge commit with TWO parents (distinguishes merge from regular commit)
    merge_commit = Commit(
        message = message,
        author = username,
        parent = [current_commit_hash, merge_branch_hash],  # Two parents = merge commit
        files = all_files
    )

    # Serialize, hash, and store the merge commit in objects database
    merge_commit_bytes = pickle.dumps(merge_commit)
    merge_commit_hash = hashlib.sha1(merge_commit_bytes).hexdigest()
    merge_commit_subdir = Path(".minigit") / "objects" / "commits" / merge_commit_hash[:2]
    merge_commit_subdir.mkdir(exist_ok=True)
    merge_commit_path = Path(merge_commit_subdir) / merge_commit_hash
    with open(merge_commit_path, "wb") as f:
        f.write(merge_commit_bytes)

    # ============================================================================
    # STEP 6: Update HEAD or current branch to point to the merge commit
    # ============================================================================

    head_detached = head_tuple[0]

    if head_detached:
        # Detached HEAD: Update HEAD to point directly to merge commit hash
        head_content = merge_commit_hash
        with open(".minigit/HEAD", "w") as f:
            f.write(head_content)
    else:
        # Attached HEAD: Update the branch pointer to the merge commit
        # HEAD itself stays pointing to the branch reference
        branch_name = head_tuple[2]
        branch_path = Path(".minigit") / "refs" / "heads" / branch_name
        with open(branch_path, "w") as f:
            f.write(merge_commit_hash)

