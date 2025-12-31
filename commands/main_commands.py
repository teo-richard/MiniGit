"""
MiniGit - A simplified version control system
This module contains the core commands for managing a MiniGit repository.
"""

import os
from pathlib import Path
import datetime
import pickle
import hashlib

# Commit class represents a snapshot of the repository at a point in time
class Commit:
    """
    Represents a single commit in the repository.

    Attributes:
        message: Commit message describing the changes
        parent: Hash of the parent commit (None for initial commit)
        files: Dictionary mapping filenames to their content hashes
        author: Name of the commit author
        timestamp: When the commit was created
    """
    def __init__ (self, message, parent, files, author, timestamp = datetime.datetime.now):
        self.message = message
        self.parent = parent
        self.files = files
        self.author = author
        self.timestamp = timestamp 

def create_minigit():
    """
    Initialize a new MiniGit repository in the current directory.

    Creates the .minigit directory structure with:
    - objects/commits/: Stores commit objects
    - objects/blobs/: Stores file content snapshots
    - refs/heads/: Stores branch references
    - index: Staging area for tracking changes
    - HEAD: Points to the current commit
    - master: Default branch
    """
    current_dir = Path.cwd()
    minigit_dir = current_dir / ".minigit"

    # Check if repository already exists
    if minigit_dir.exists():
        print("A gitlet folder already exists in the cwd you fooooool")
        return

    # Create .minigit/
    minigit_dir.mkdir() 
    # Create subdirectories
    (minigit_dir / "objects").mkdir() 
    (minigit_dir / "objects" / "commits").mkdir() 
    (minigit_dir / "objects" / "blobs").mkdir() 
    (minigit_dir / "refs" / "heads").mkdir(parents=True)

    # Create instance of Commit class
    initial_commit = Commit(
        message = "initial commit",
        author = "Probably not a Martian",
        parent = None,
        files = {}
    )


    # Serialize the commit (i.e. convert to bytes)
    initial_commit_data = pickle.dumps(initial_commit)

    # Hash the commit by chaining hashlib.sha1() to hexdigest()
    initial_commit_hash = hashlib.sha1(initial_commit_data).hexdigest()

    # Create file that will contain your initial commit object (with hash as filename)
    # Storing initial_commit_hash in a folder named using the first two characters of the hash
    object_subdir = minigit_dir / "objects" / "commits" / initial_commit_hash[:2]
    object_subdir.mkdir()
    commit_file = object_subdir / initial_commit_hash

    # Write it to the correct directory
    # Write the initial commit data (your commit dictionary repr. as bytes) in the initial commit file
    with open(commit_file, "wb") as f: # "wb" for writing bytes
        f.write(initial_commit_data)

    # Create master branch
    master_branch = minigit_dir / "refs" / "heads" / "master"
    with open(master_branch, "w") as f: # "w" for writing text
        f.write(initial_commit_hash)

    # Create HEAD
    HEAD = minigit_dir / "HEAD"
    with open(HEAD, "w") as f:
        f.write(initial_commit_hash)

    # Create empty staging area
    index_file = minigit_dir / "index" # Creates a path object
    empty_dict = {"additions": {}, "removals": []} # Create empty dictionary to be filled later

    # Create index_file as a FILE and put the empty dictionary in there
    with open(index_file, "wb") as f:
        pickle.dump(empty_dict, f) # Pickles the empty_dict and puts it in the file
    
    print("Initialized MiniGit repository. Go ham.")


def stage(files, type):
    """
    Add files to or remove files from the staging area.

    Args:
        files: Single filename (str) or list of filenames to stage
        type: Either "additions" (to stage files) or "removals" (to mark files for deletion)

    The staging area (index) tracks changes to be included in the next commit.
    Files are hashed using SHA-1 to detect changes.
    """
    # Convert single file to list for uniform processing
    filelist = []
    index_file = Path(".minigit") / "index"
    if isinstance(files, str):
        filelist.append(files)
    else:
        filelist = files

    # Load current staging area from index file
    with open(index_file, "rb") as f:
        staging = pickle.load(f)

    # Process each file
    for filename in filelist:
        filepath = Path(filename)

        # Validate file exists
        if not filepath.exists():
            print(f"File {filename} does not exist")

        # Read file content and compute hash
        with open(filepath, "rb") as f:
            file_content = f.read()

        file_hash = hashlib.sha1(file_content).hexdigest()

        # Add to appropriate staging section
        # We also know that if a file is already in staging area, it will get the hash we just created :)
        if type == "additions":
            staging["additions"][filename] = file_hash
        elif type == "removals":
            staging["removals"].append(filename)

    # Save updated staging area back to index
    staging_bytes = pickle.dumps(staging)

    with open(index_file, "wb") as f:
        f.write(staging_bytes)

def empty():
    empty_dict = {"additions": {}, "removals": []}

    with open(".minigit/index", "wb") as f:
        pickle.dump(empty_dict, f)


def commit():
    """
    Create a new commit from the current staging area.

    This function:
    1. Loads the staging area to see what changes need to be committed
    2. Retrieves the parent commit (current HEAD)
    3. Merges parent files with staged additions/removals
    4. Creates a new commit object
    5. Saves it to the objects directory
    6. Updates HEAD to point to the new commit

    Note: This function appears to be incomplete.
    """
    # Load the staging area
    with open(".minigit/index", "rb") as f:
        staging_area = pickle.load(f)

    # Get the hash of the most recent commit (parent commit)
    with open(".minigit/HEAD", "rb") as f:
        recent_commit_hash = f.read()

    # Load the parent commit object
    recent_commit_object_path = Path(".minigit") / HEAD / recent_commit_hash[:2] / recent_commit_hash
    with open(recent_commit_object_path, "rb") as f:
        recent_commit_object = pickle.load(f)

    # Extract files from parent commit
    recent_commit_files = recent_commit_object.files # Dictionary of {filename: file_hash}
    # Extract the file names
    recent_commit_filenames = list(recent_commit_files.keys()) # Just the file names

    # Extract files from staging area that are additions (not removals)
    staging_area_additions = staging_area["additions"] # Dictionary of {filename: file_hash}
    # Extract the file names
    staging_area_additions_filenames = list(staging_area_additions.keys()) # Just the file names

    # Get files in the recent commit but not in the staging area
    exists_recent_commit_only = [x for x in recent_commit_filenames if x not in staging_area_additions_filenames]
    files_brought_over = {k: v for k, v in recent_commit_files.items() if k in exists_recent_commit_only}

    new_staging_area_additions = staging_area_additions
    for file in files_brought_over:
        new_staging_area_additions[file] = files_brought_over[file]

    staging_area["additions"] = new_staging_area_additions

    with open(".minigit/index", "wb") as f:
        pickle.dump(staging_area, f)


    

