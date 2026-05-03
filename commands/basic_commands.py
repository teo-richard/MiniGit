"""
Basic utility commands for MiniGit.
"""

import pickle
import utils
from pathlib import Path
from utils import Commit
import getpass



def empty():
    """
    Clear the staging area by resetting the index file.

    The staging area tracks:
    - additions: Files to be added/modified in next commit
    - removals: Files to be removed in next commit

    This function resets both to empty, effectively unstaging all changes.
    """
    # Create empty staging area structure
    empty_dict = {}
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
    """
    filelist = utils.files_to_list(files)
    with open(".minigitignore", 'a') as f:
        f.write('\n'+'\n'.join(filelist))



def empty_file(files):
    """
    Unstage one or more files.

    Args:
        files: Either a single filename (str) or list of filenames to unstage

    - If the file is staged as an addition, it is removed from the index.
    - If the file was staged for removal (deleted from the index), it is restored
      from the HEAD commit back into the index.
    - If the file is neither staged nor in HEAD, an error is printed.
    """
    filelist = utils.files_to_list(files)

    staging_area = utils.get_staging_area()

    head_hash = utils.check_head()[4]
    head_commit_files = utils.get_commit(head_hash).files if head_hash else {}

    for file in filelist:
        if file in staging_area:
            del staging_area[file]
        elif file in head_commit_files:
            # File was staged for removal — restore it from HEAD
            staging_area[file] = head_commit_files[file]
        else:
            print(f"Cannot remove {file} from staging area. Check if file is actually in staging area.")

    with open(".minigit/index", "wb") as f:
        pickle.dump(staging_area, f)
