import os
from pathlib import Path
import datetime
import pickle
import hashlib

def create_gitlet():
    current_dir = Path.cwd()
    gitlet_dir = current_dir / ".gitlet"

    if gitlet_dir.exists():
        print("A gitlet folder already exists in the cwd you fooooool")
        return

    # Create .gitlet./
    gitlet_dir.mkdir() 
    # Create subdirectories
    (gitlet_dir / "objects").mkdir() 
    (gitlet_dir / "refs" / "heads").mkdir(parents=True)

    # Dictionary containing initial commit information
    initial_commit = {
        "message": "initial commit",
        "timestamp": datetime.datetime.now(),
        "parent": None,
        "files": {}
    }

    # Serialize the commit (i.e. convert to bytes)
    initial_commit_data = pickle.dumps(initial_commit)

    # Hash the commit by chaining hashlib.sha1() to hexdigest()
    initial_commit_hash = hashlib.sha1(initial_commit_data).hexdigest()

    # Create file that will contain your initial commit object (with hash as filename)
    # Storing initial_commit_hash in a folder named using the first two characters of the hash
    object_subdir = gitlet_dir / "objects" / initial_commit_hash[:2]
    object_subdir.mkdir()
    commit_file = object_subdir / initial_commit_hash

    # Write it to the correct directory
    # Write the initial commit data (your commit dictionary repr. as bytes) in the initial commit file
    with open(commit_file, "wb") as f: # "wb" for writing bytes
        f.write(initial_commit_data)

    # Create master branch
    master_branch = gitlet_dir / "refs" / "heads" / "master"
    with open(master_branch, "w") as f: # "w" for writing text
        f.write(initial_commit_hash)


    # Create empty staging area
    index_file = gitlet_dir / "index" # Creates a path object
    empty_dict = {} # Write empty dictionary to the file to be filled later

    # Create index_file as a FILE and put the empty dictionary in there
    with open(index_file, "wb") as f:
        pickle.dump(empty_dict, f) # Pickles the empty_dict and puts it in the file
    
    print("Initialized MiniGit repository. Go ham. ")

