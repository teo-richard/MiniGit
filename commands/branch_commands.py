from pathlib import Path
import datetime
import pickle
import hashlib
import getpass
import utils

# Does checkout for a commit. See branch_commands.py branch_switch() for checking out a branch.
def checkout_commit(checkout_hash):
    # Get the commit object
    commit_subdr_path = Path(".minigit") / "objects" / "commits" / checkout_hash[:2]
    commit_subdr_path.mkdir(exist_ok = True)
    commit_path = commit_subdr_path / checkout_hash

    with open(commit_path, "rb") as f:
        commit_object = pickle.load(f)
    
    commit_files = commit_object.files

    # Update your files
    for filename, hash in commit_files.items():
        # Getting the old blob
        blob_path = Path(".minigit") / "objects" / "blobs" / hash[:2] / hash
        with open(blob_path, "rb") as f:
            blob = f.read() # Your file is read in in binary form
        
        # Rewriting the current file with the file from the blob
        with open(filename, "wb") as f:
            f.write(blob)

    # Update head
    # Head is detached since we're checking out a commit not a branch
    with open(".minigit/HEAD", "w") as f:
        f.write(checkout_hash)


def branch_switch():
    # not started yet