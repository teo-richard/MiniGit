"""
History manipulation commands for MiniGit.
Provides commands to revert to previous commits and reset repository state.
"""

import pathlib as Path
import pickle
import getpass
import utils
from utils import Commit
import hashlib
from commands import main_commands, basic_commands

def revert(hash, message):
    """
    Revert the repository to a previous commit's state by creating a new commit.

    Unlike reset, revert is a safe operation that preserves history. It creates
    a new commit that contains the same files as the target commit, leaving
    the commit history intact.

    Args:
        hash: The SHA-1 hash of the commit to revert to
        message: Optional commit message for the revert commit.
                 If None, defaults to "Reverting to commit {hash}."

    Process:
        1. Restores working directory files to match the target commit
        2. Stages all files from the target commit
        3. Creates a new commit with the reverted state
    """
    head_tuple = utils.check_head()
    head_hash = head_tuple[4]
    tracked_files = utils.get_commit(head_hash).files

    # Restore working directory to match the target commit
    utils.get_old_commit_state(hash, tracked_files)

    # Load the target commit to get its file list
    revert_commit_object = utils.get_commit(hash)
    revert_commit_files = revert_commit_object.files

    # Clear the staging area before staging the reverted files
    basic_commands.empty()

    # Stage all files from the target commit
    with open(".minigit/index", "rb") as f:
        staging = pickle.load(f)

    for file, hash in revert_commit_files.items():
        staging["additions"][file] = hash

    with open(".minigit/index", "wb") as f:
        pickle.dump(staging, f)

    # Create the revert commit with default message if none provided
    if message == None:
        message = f"Reverting to commit {hash}."
    main_commands.commit(message)


def reset():
    """
    Reset the repository to a previous commit, destroying history.

    WARNING: This is a destructive operation. Unlike revert, reset removes
    all commits after the target commit from history.

    Not yet implemented.
    """
    pass