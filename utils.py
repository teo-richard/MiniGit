"""
Utility functions for MiniGit operations.
"""

from datetime import datetime
from pathlib import Path
import pickle
import hashlib
import os

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
        for filename, hash in file_dictionary.items():
            blob_path = Path(".minigit") / "objects" / "blobs" / hash[:2] / hash
            with open(blob_path, "rb") as f:
                filecontent = f.read()
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
    Check if a file path should be ignored by MiniGit.

    Ignores:
    - Python cache files (__pycache__, .pyc)
    - Virtual environments (venv/)
    - Git repositories (.git, .minigit)
    - System files (.DS_Store)
    - Hidden files/directories (starting with .)

    Args:
        filepath: Path to check

    Returns:
        bool: True if file should be ignored, False otherwise
    """
    # List of patterns to ignore
    ignore_patterns = [
        '__pycache__',
        '.pyc',
        'venv/',
        '.git',
        '.minigit',
        '.DS_Store',
    ]

    # Check if any ignore pattern is in the filepath
    for pattern in ignore_patterns:
        if pattern in filepath:
            return True

    # Also ignore any hidden files/directories (starting with .)
    parts = filepath.split(os.sep)
    if any(part.startswith(".") and part != "." for part in parts):
        return True

    return False

def get_directory_files_dictionary():
    """
    Create a dictionary mapping all non-ignored files to their SHA-1 hashes.

    This function walks the entire working directory, filters out ignored files,
    and computes content hashes for tracking file changes.

    Returns:
        dict: Dictionary mapping normalized file paths to their SHA-1 hashes
    """
    # Dictionary to store all files in working directory with their content hashes
    directory_files = {}

    # Walk through all files in the working directory and compute their hashes
    # `dirs` is os.walk's internal list of dirs it will walk to in the starting folder
    for root, dirs, files in os.walk("."):
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

