"""
History manipulation commands for MiniGit.
Provides commands to revert to previous commits and reset repository state.
"""

import pickle
import getpass
import utils
from utils import Commit, CommitNotFoundError
import hashlib
from commands import main_commands, basic_commands

@utils.check_uncommitted_changes
def revert(commit_hash, message):
    """
    Revert the repository to a previous commit's state by creating a new commit.

    Unlike reset, revert is a safe operation that preserves history. It creates
    a new commit that contains the same files as the target commit, leaving
    the commit history intact.

    Args:
        commit_hash: The SHA-1 hash of the commit to revert to
        message: Optional commit message for the revert commit.
                 If None, defaults to "Reverting to commit {commit_hash}."

    Process:
        1. Restores working directory files to match the target commit
        2. Stages all files from the target commit
        3. Creates a new commit with the reverted state
    """
    # Restore working directory to match the target commit

    tracked_files = utils.get_tracked_files() # Getting files in the most recent commit
    utils.get_old_commit_state(commit_hash, tracked_files) # Going back to the state of the user-inputted commit

    # Load the target commit to get its file list
    revert_commit_object = utils.get_commit(commit_hash)
    revert_commit_files = revert_commit_object.files

    # Clear the staging area before staging the reverted files
    basic_commands.empty()

    # Stage all files from the target commit
    staging_area = utils.get_staging_area()

    for file, blob_hash in revert_commit_files.items():
        staging_area[file] = blob_hash # Resetting to the correct hash


    with open(".minigit/index", "wb") as f:
        pickle.dump(staging_area, f)

    # Create the revert commit with default message if none provided
    if message == None:
        message = f"Reverting to commit {commit_hash}."
    main_commands.commit(message)



@utils.check_uncommitted_changes
def reset(hash, type):
    """
    Reset the repository to a previous commit, destroying history.

    WARNING: This is a destructive operation. Unlike revert, reset removes
    all commits after the target commit from history.
    """
    # Get tracked files
    tracked_files = utils.get_tracked_files()

    if type == "hard":
        # Put the wd in the state of the commit the user is resetting to
        utils.get_old_commit_state(hash, tracked_files)
        basic_commands.empty()

    # Update the branch
    head_tuple = utils.check_head()
    head_detached = head_tuple[0]
    if head_detached:
        with open(".minigit/HEAD", "w") as f:
            f.write(hash)
        print("\nWarning: HEAD is still in detached state.\n")
    else:
        branch_path = head_tuple[3] # Path to the hash in the branch currently
        with open(branch_path, "w") as f:
            f.write(hash)
        
    