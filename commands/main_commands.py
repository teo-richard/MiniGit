"""
MiniGit - A simplified version control system
This module contains the core commands for managing a MiniGit repository.
init, stage, empty, commit
"""

from pathlib import Path
import datetime
import pickle
import hashlib
import getpass
import utils
from utils import Commit


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
    # Get current working directory and construct path to .minigit directory
    current_dir = Path.cwd()
    minigit_dir = current_dir / ".minigit"

    # Check if repository already exists to avoid overwriting
    if minigit_dir.exists():
        print("A MiniGit folder already exists in the cwd you fooooool")
        return

    # Create .minigit directory and all necessary subdirectories
    minigit_dir.mkdir()
    (minigit_dir / "objects").mkdir()  # Root directory for all object storage
    (minigit_dir / "objects" / "commits").mkdir()  # Stores serialized commit objects
    (minigit_dir / "objects" / "blobs").mkdir()  # Stores actual file content snapshots
    (minigit_dir / "refs" / "heads").mkdir(parents=True)  # Stores branch pointers (parents=True creates intermediate dirs)
    # Note: HEAD is created later as a file, not a directory

    # Get the author using getpass to get the username
    username = getpass.getuser()

    # Create the initial commit object (empty repository state)
    initial_commit = Commit(
        message = "initial commit",
        author = username,
        parent = [],  # No parent since this is the first commit
        files = {}  # No files tracked in initial commit
    )

    # Serialize the commit object to bytes using pickle
    # This converts the Python object to a byte stream that can be stored on disk
    initial_commit_data = pickle.dumps(initial_commit)

    # Generate SHA-1 hash of the commit data to create a unique identifier
    # This hash serves as the commit ID and filename
    initial_commit_hash = hashlib.sha1(initial_commit_data).hexdigest()

    # Create subdirectory using first 2 characters of hash (git-style optimization)
    # This prevents having too many files in a single directory
    # e.g., if hash is "abc123...", creates ".minigit/objects/commits/ab/"
    object_subdir = minigit_dir / "objects" / "commits" / initial_commit_hash[:2]
    object_subdir.mkdir()
    commit_file = object_subdir / initial_commit_hash

    # Write the serialized commit data to the commit file
    # The file is named using the full commit hash
    with open(commit_file, "wb") as f:  # "wb" mode for writing binary data
        f.write(initial_commit_data) # initial_commit_data is in bytes

    # Create the master branch and make it point to the initial commit
    # Branch files contain the hash of the commit they point to
    master_branch = minigit_dir / "refs" / "heads" / "master"
    with open(master_branch, "w") as f:  # "w" mode for writing text
        f.write(initial_commit_hash) # the hash is just text

    # Create HEAD file to track current commit and branch
    # HEAD stores [current_commit_hash, current_branch_name]
    HEAD_path = minigit_dir / "HEAD"
    head_content = "ref: refs/heads/master" # Stored like this for portability
    with open(HEAD_path, "w") as f:
        f.write(head_content)  # Store as pickled list for easy modification later

    # Create empty staging area (index)
    # The index tracks files to be added or removed in the next commit
    index_file = minigit_dir / "index"
    empty_dict = {"additions": {}, "removals": []}  # additions: {filename: hash}, removals: [filename]

    # Write the empty staging area structure to disk
    with open(index_file, "wb") as f:
        pickle.dump(empty_dict, f)  # Serialize and write the empty dictionary

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
    # Normalize input to a list for consistent processing
    # Allows function to accept both single file (str) and multiple files (list)
    filelist = []
    index_file = Path(".minigit") / "index"
    if isinstance(files, str):
        filelist.append(files)  # Convert single file to list
    else:
        filelist = files  # Already a list

    # Load the current staging area from the index file
    # The index contains: {"additions": {filename: hash}, "removals": [filename]}
    with open(index_file, "rb") as f:
        staging = pickle.load(f)

    # Process each file to be staged
    for filename in filelist:
        filepath = Path(filename)

        # Check if the file exists before trying to stage it
        if not filepath.exists():
            print(f"File {filename} does not exist")
            continue  # Skip to next file

        # Read the file content in binary mode
        with open(filepath, "rb") as f:
            file_content = f.read()

        # Generate SHA-1 hash of file content for change detection
        # This hash allows us to track if file content has changed
        file_hash = hashlib.sha1(file_content).hexdigest()

        # Normalize the filename to ensure consistent path format
        # Remove leading './' and convert backslashes to forward slashes
        normalized_filename = str(filepath).lstrip("./").replace("\\", "/")

        # Add file to the appropriate section of the staging area
        # If file is already staged, its hash will be updated
        if type == "additions":
            staging["additions"][normalized_filename] = file_hash  # Store as {filename: hash}
        elif type == "removals":
            staging["removals"].append(normalized_filename)  # Store in list

    # Serialize the updated staging area back to bytes
    staging_bytes = pickle.dumps(staging)

    # Write the updated staging area back to the index file
    with open(index_file, "wb") as f:
        f.write(staging_bytes) # already in bytes so don't need pickle.dump



def commit(commit_message):
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
    # Load the current staging area to see what changes are ready to commit
    with open(".minigit/index", "rb") as f:
        staging_area = pickle.load(f)

    # Update the branch to point to the new commit if head is not detached
    # Get branch from head
    head_tuple = utils.check_head()
    prev_commit_hash = head_tuple[4]


    # Construct the path to the previous commit object
    # Commits are stored in subdirectories based on first 2 chars of hash
    previous_commit_object_path = Path(".minigit") / "objects" / "commits" / prev_commit_hash[:2] / prev_commit_hash
    with open(previous_commit_object_path, "rb") as f:
        previous_commit_object = pickle.load(f)

    # Extract the file tracking dictionary from the parent commit
    # This shows all files that existed in the previous commit
    previous_commit_files = previous_commit_object.files  # Dictionary of {filename: file_hash}
    previous_commit_filenames = list(previous_commit_files.keys())  # Extract just the filenames

    # Extract files from staging area that are being added/modified
    staging_area_additions = staging_area["additions"]  # Dictionary of {filename: file_hash}
    staging_area_additions_filenames = list(staging_area_additions.keys())  # Extract just the filenames

    # Find files that exist in the previous commit but NOT in staging area
    # These files haven't been modified, so they should carry over to the new commit
    exists_previous_commit_only = [x for x in previous_commit_filenames if x not in staging_area_additions_filenames]

    # Create a dictionary of files to carry over from previous commit
    # These are unchanged files that need to persist in the new commit
    files_brought_over = {k: v for k, v in previous_commit_files.items() if k in exists_previous_commit_only}

    # Merge the carried-over files with the staging area additions
    # This creates the complete file list for the new commit
    new_staging_area_additions = staging_area_additions
    for file in files_brought_over:
        new_staging_area_additions[file] = files_brought_over[file]

    # Update the staging area additions with the merged file list
    staging_area["additions"] = new_staging_area_additions

    # Get a final staging area where we have:
    #   all the additions (files changed and put in staging area by user and unchanged files that must persist)
    #   take out the files in removals that the user wants to not include in this commit
    final_staging_area = {k: v for k, v in staging_area["additions"].items() if k not in staging_area["removals"]}


    # Writing the updated staging area dictionary to index
    with open(".minigit/index", "wb") as f:
        pickle.dump(staging_area, f)

    # Get username
    username = getpass.getuser()
    
    # Create new commit object
    new_commit = Commit(
        message = commit_message,
        author = username,
        parent = [prev_commit_hash],
        files = final_staging_area
    )

    new_commit_bytes = pickle.dumps(new_commit)
    new_commit_hash = hashlib.sha1(new_commit_bytes).hexdigest()

    # Write new commit object to the commits directory
    # Create subdirectory using first 2 characters of hash (if it doesn't exist)
    object_subdir = Path(".minigit") / "objects" / "commits" / new_commit_hash[:2]
    object_subdir.mkdir(exist_ok=True)  # Create directory only if it doesn't exist
    new_commit_path = object_subdir / new_commit_hash

    with open(new_commit_path, "wb") as f:
        f.write(new_commit_bytes)
    
    # Update the branch to point to the new commit if head is not detached
    
    head_tuple = utils.check_head()
    branch_path = head_tuple[3]
    branch_name = head_tuple[2]
    head = head_tuple[1]
    if head_tuple[0] == True:
        print(f"\nNote: head is detached at {new_commit_hash}.")
        with open(".minigit/HEAD", "w") as f:
            f.write(new_commit_hash) # Head is detached still, so just put this new commit hash
    else:
        new_branch_hash = new_commit_hash
        with open(branch_path, "w") as f:
            f.write(new_branch_hash)
        new_head = f"ref: refs/heads/{branch_name}"
        with open(".minigit/HEAD", "w") as f:
            f.write(new_head)
        print(f"\nHead points to {head} and you are on branch {branch_name}.")
    



    print("Files committed:")
    # Update the blobs
    for filename, hash in final_staging_area.items():
        # Get the blob
        with open(filename, "rb") as f:
            blob = f.read()

        # Get the correct path
        blob_subdir_path = Path(".minigit") / "objects" / "blobs" / hash[:2]
        blob_subdir_path.mkdir(exist_ok = True)
        blob_path = blob_subdir_path / hash

        with open(blob_path, "wb") as f:
            f.write(blob) # Blob is already in bytes as we read it in as bytes
        print(f"     {filename}")

    print("\nStaging area has been emptied. Congratulations on your commit!\n")

    
