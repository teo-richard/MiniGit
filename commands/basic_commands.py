"""
Basic utility commands for MiniGit.
"""

import pickle
import utils

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

def mgignore(files):
    """
    Add file patterns to the .minigitignore file.

    Writes the specified file patterns to .minigitignore, which determines
    which files should be excluded from tracking.

    Args:
        files: Single filename/pattern (str) or list of filenames/patterns to ignore

    Note:
        This overwrites the existing .minigitignore content rather than appending.
    """
    filelist = utils.files_to_list(files)
    with open(".minigitignore", 'w') as f:
        f.write('\n'.join(filelist))

def empty_file(files):
    """
    Remove one or more files from the staging area.

    Args:
        files: Either a single filename (str) or list of filenames to unstage

    This will remove the file from either additions or removals in the staging area.
    Supports selective unstaging of multiple files in one operation.
    """
    filelist = utils.files_to_list(files)

    # Load current staging area
    with open(".minigit/index", "rb") as f:
            staging = pickle.load(f)

    # Process each file to unstage
    for file in filelist:
        # Check if file is staged for removal and remove it from that list
        if file in staging["removals"]:
            staging["removals"].remove(file)
        else:
            # Otherwise try to remove from additions, catching case where file isn't staged
            try:
                staging["additions"].pop(file)
            except KeyError:
                # Provide helpful error message if file isn't actually in staging area
                print(f"Cannot remove {file} from staging area. Check if file is actually in staging area.")

        # Write updated staging area back to disk after each file
        with open(".minigit/index", "wb") as f:
            pickle.dump(staging, f)
