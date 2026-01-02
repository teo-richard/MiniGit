"""
Basic utility commands for MiniGit.
"""

import pickle

def empty():
    """
    Clear the staging area by resetting the index file.

    The staging area tracks:
    - additions: Files to be added/modified in next commit
    - removals: Files to be removed in next commit

    This function resets both to empty, effectively unstaging all changes.
    """
    # Create empty staging area structure
    empty_dict = {"additions":{}, "removals":[]}
    # Write empty structure to index file
    with open(".minigit/index", "wb") as f:
        pickle.dump(empty_dict, f)
