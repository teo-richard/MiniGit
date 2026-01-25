"""
Utility functions for MiniGit operations.
"""

from datetime import datetime
from pathlib import Path
import pickle
import hashlib
import os
import fnmatch

# Commit class represents a snapshot of the repository at a point in time
class Commit:
    """
    Represents a single commit in the repository.

    Attributes:
        message: Commit message describing the changes
        parent: List of parent commit hashes (empty list for initial commit, one parent for normal commits, multiple parents for merge commits)
        files: Dictionary mapping filenames to their content hashes
        author: Name of the commit author
        timestamp: When the commit was created
    """
    def __init__ (self, message, parent, files, author, timestamp = None):
        self.message = message
        self.parent = parent
        self.files = files
        self.author = author
        self.timestamp = timestamp if timestamp is not None else datetime.now() 

def write_files_from_dictionary(file_dictionary):
    """
    Restore files to the working directory from their blob storage.

    Takes a dictionary mapping filenames to blob hashes and writes each file's
    content from the blob storage back to the working directory.

    Args:
        file_dictionary: Dictionary mapping {filename: blob_hash}
    """
    for filename, hash in file_dictionary.items():
        # Construct path to the blob using the hash-based directory structure
        blob_path = Path(".minigit") / "objects" / "blobs" / hash[:2] / hash
        # Read the blob content (original file content)
        with open(blob_path, "rb") as f:
            filecontent = f.read()
        # Write the content back to the working directory
        filepath = Path(filename)
        with open(filepath, "wb") as f:
            f.write(filecontent)



def check_head():
    """
    Check the current HEAD state and return relevant information.

    HEAD can be in two states:
    1. Attached: Points to a branch reference (e.g., "ref: refs/heads/master")
    2. Detached: Points directly to a commit hash

    Returns:
        tuple: A 5-element tuple containing:
            - head_detached (bool): True if HEAD is detached, False if attached to branch
            - head (str or None): Branch reference path (e.g., "refs/heads/master") or None if detached
            - branch_name (str or None): Name of current branch or None if detached
            - hash_path (Path or None): Path to branch reference file or None if detached
            - hash (str): Current commit hash
    """
    # Read HEAD file to determine current state
    with open(".minigit/HEAD", "r") as f:
        head_content = f.read().strip()

    # Check if HEAD is detached (contains only hash) or attached (contains "ref: refs/heads/...")
    if "refs" not in head_content:  # If HEAD is detached
        head_detached = True
        head = None
        branch_name = None
        hash_path = None
        hash = head_content  # HEAD directly contains the commit hash
    else:  # HEAD is attached to a branch
        head_detached = False
        # Parse branch reference from "ref: refs/heads/branch_name"
        head = head_content.split()[1]  # Extract "refs/heads/branch_name"
        branch_name = head.split("/")[-1]  # Extract just "branch_name"
        # Get path to branch file and read the commit hash it points to
        hash_path = Path(".minigit") / "refs" / "heads" / branch_name
        with open(hash_path, "r") as f:
            hash = f.read().strip()

    return head_detached, head, branch_name, hash_path, hash


def files_to_list(files):
    """
    Normalize file input to always return a list.

    This utility function handles both single file (str) and multiple files (list) input,
    converting them to a consistent list format for uniform processing.

    Args:
        files: Either a string (single file) or list of strings (multiple files)

    Returns:
        list: Normalized list of filenames
    """
    filelist = []
    if isinstance(files, str):
        filelist.append(files)  # Convert single file to list
    else:
        filelist = files  # Already a list

    return filelist

def check_ignore(filepath):
    """
    Check if a file should be ignored based on .minigitignore patterns.

    Uses fnmatch for glob-style pattern matching. Supports:
    - Exact filenames (e.g., "secret.txt")
    - Wildcard patterns (e.g., "*.log", "temp_*")
    - Directory patterns ending with "/" (e.g., "build/")
    - Comments in .minigitignore starting with "#"

    Args:
        filepath: The file path to check against ignore patterns

    Returns:
        bool: True if the file should be ignored, False otherwise
    """
    # Built-in patterns that are always ignored (MiniGit's internal files)
    builtin_patterns = [
        ".minigit/",
        ".minigitignore"
    ]
    with open(".minigitignore", "r") as f:
        mgignore = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]

    # Combine user patterns with built-in patterns
    ignore_patterns = mgignore + builtin_patterns

    # Check each component of the path against ignore patterns
    # This allows patterns like "node_modules" to match "src/node_modules/file.js"
    fileparts = filepath.split("/")
    for part in fileparts:
        for pattern in ignore_patterns:
            ignore = fnmatch.fnmatch(part, pattern)
            if ignore:
                return True
            else:
                continue
    # Check the full filepath against patterns
    for pattern in ignore_patterns:
            # Directory patterns (ending with /) match paths that start with the pattern
            if pattern.endswith("/"):
                if filepath.startswith(pattern):
                    return True
            else:
                ignore = fnmatch.fnmatch(filepath, pattern)
                if ignore:
                    return True
                else:
                    continue
    
    return False


    

def get_directory_files_dictionary(subdir):
    """
    Create a dictionary mapping all non-ignored files to their SHA-1 hashes. (see check_ignore() function right above this)

    This function walks the entire working directory, filters out ignored files,
    and computes content hashes for tracking file changes.

    Returns:
        dict: Dictionary mapping normalized file paths to their SHA-1 hashes
    """
    # Dictionary to store all files in working directory with their content hashes
    directory_files = {}

    # Walk through all files in the working directory and compute their hashes
    # `dirs` is os.walk's internal list of dirs it will walk to in the starting folder
    for root, dirs, files in os.walk(subdir):
        for file in files:
            # Filter out directories that should be ignored (modifies dirs in-place)
            # This prevents os.walk from descending into ignored directories
            dirs[:] = [d for d in dirs if not check_ignore(d)]
            filepath = os.path.join(root, file)
            # Skip individual files that should be ignored
            if check_ignore(filepath) == True:
                continue
            # Read file contents in binary mode to compute hash
            with open(filepath, "rb") as f:
                file_byte = f.read()

            # Compute SHA-1 hash to detect file changes
            file_hash = hashlib.sha1(file_byte).hexdigest()
            # Normalize path to remove leading './' and use forward slashes for consistency
            normalized_path = filepath.lstrip("./").replace("\\", "/")
            directory_files[normalized_path] = file_hash

    return directory_files


def make_blob_current(files_dictionary):
    """
    Restore files from blob storage to the working directory.

    Similar to write_files_from_dictionary but used specifically during
    checkout operations to make the working directory match a commit's state.

    Args:
        files_dictionary: Dictionary mapping {filename: blob_hash}
    """
    for filename, hash in files_dictionary.items():
        # Construct path to blob using hash-based directory structure
        blob_path = Path(".minigit") / "objects" / "blobs" / hash[:2] / hash
        # Read blob content
        with open(blob_path, "rb") as f:
            blob = f.read()
        # Write to working directory
        with open(filename, "wb") as f:
            f.write(blob)

# Custom exception class
class CommitNotFoundError(Exception):
    pass

def get_commit(hash):
    """
    Load and return a commit object from the objects database.

    Args:
        hash: The SHA-1 hash of the commit to retrieve

    Returns:
        Commit: The deserialized Commit object
    """
    # Commits are stored in subdirectories using first 2 chars of hash for organization
    path_to_commit = Path(".minigit") / "objects" / "commits" / hash[:2] / hash
    if path_to_commit.exists():
        with open(path_to_commit, "rb") as f:
            prev_commit_obj = pickle.load(f)

        return prev_commit_obj
    else:
        raise CommitNotFoundError(f"Error: Commit {hash} not found. ")


def get_old_commit_state(hash, tracked_files):
    """
    Restore the working directory to match a specific commit's state.

    This function is used during checkout/revert operations to make the
    working directory match a historical commit. It restores files from
    the commit and removes files that shouldn't exist at that point.

    Args:
        hash: The SHA-1 hash of the commit to restore
        tracked_files: Dictionary of currently tracked files {filename: hash}
                      Used to determine which files need to be deleted
    """
    commit_object = get_commit(hash)
    # Extract the file mappings (filename -> blob hash) from the commit
    commit_files = commit_object.files
    # Restore all files from the commit to the working directory
    make_blob_current(commit_files)

    # Delete files that are currently tracked but don't exist in the target commit
    # This ensures the working directory exactly matches the commit state
    delete_files = [i for i in tracked_files.keys() if i not in commit_files.keys()]
    for file in delete_files:
        if os.path.exists(file):
            os.remove(file)


def get_tracked_files():
    # Get the files currently being tracked
    head_tuple = check_head()
    head_hash = head_tuple[4]
    previous_commit_object = get_commit(head_hash)
    tracked_files = previous_commit_object.files
    return tracked_files
