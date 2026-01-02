"""
Utility functions for MiniGit operations.
"""

from pathlib import Path

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
        head_content = f.read()

    # Check if HEAD is detached (contains only hash) or attached (contains "ref: refs/heads/...")
    if " " not in head_content:  # If HEAD is detached
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
            hash = f.read()

    return head_detached, head, branch_name, hash_path, hash