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

def minigitignore():
    pass

def empty_file(filename):
    """
    Remove a specific file from the staging area.

    Args:
        filename: The file to unstage

    This will remove the file from either additions or removals in the staging area.
    If the index file is empty or corrupted, it initializes a new staging area.
    """
    try:
        with open(".minigit/index", "rb") as f:
            staging = pickle.load(f)
    except (EOFError, FileNotFoundError):
        # If the file is empty or doesn't exist, initialize empty staging area
        staging = {"additions": {}, "removals": []}

    if filename in staging["removals"]:
        staging["removals"].remove(filename)
    elif filename in staging["additions"]:
        staging["additions"].pop(filename)
    else:
        print(f"Warning: '{filename}' is not in the staging area.")
        return

    with open(".minigit/index", "wb") as f:
         pickle.dump(staging, f)
