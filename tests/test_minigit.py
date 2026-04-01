"""
*** ALL TESTS WRITTEN BY CLAUDE CODE ***

Tests for MiniGit - a simple version control system.

Each test that requires a repo uses the `repo` fixture, which initialises a
fresh MiniGit repository in a temporary directory and changes the working
directory to it for the duration of the test.
"""

import hashlib
import os
import pickle
import sys
from pathlib import Path

import pytest

# Make sure the project root is importable regardless of where pytest is run from
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import utils
from utils import Commit, CommitNotFoundError
from commands import basic_commands, main_commands, branch_commands


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Create an initialised MiniGit repo in a temp directory."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    return tmp_path


@pytest.fixture
def repo_with_file(repo):
    """Repo that has one file staged and committed."""
    f = repo / "hello.txt"
    f.write_text("hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first real commit")
    basic_commands.empty()
    return repo


# ---------------------------------------------------------------------------
# Commit dataclass
# ---------------------------------------------------------------------------

class TestCommit:
    def test_commit_stores_attributes(self):
        c = Commit("msg", ["abc"], {"file.txt": "deadbeef"}, "alice")
        assert c.message == "msg"
        assert c.parent == ["abc"]
        assert c.files == {"file.txt": "deadbeef"}
        assert c.author == "alice"

    def test_commit_timestamp_defaults_to_now(self):
        from datetime import datetime
        before = datetime.now()
        c = Commit("msg", [], {}, "bob")
        after = datetime.now()
        assert before <= c.timestamp <= after

    def test_commit_accepts_explicit_timestamp(self):
        from datetime import datetime
        ts = datetime(2024, 1, 1)
        c = Commit("msg", [], {}, "bob", timestamp=ts)
        assert c.timestamp == ts


# ---------------------------------------------------------------------------
# utils.files_to_list
# ---------------------------------------------------------------------------

class TestFilesToList:
    def test_string_becomes_single_element_list(self):
        assert utils.files_to_list("foo.txt") == ["foo.txt"]

    def test_list_is_returned_unchanged(self):
        files = ["a.txt", "b.txt"]
        assert utils.files_to_list(files) is files

    def test_empty_list_is_returned_unchanged(self):
        assert utils.files_to_list([]) == []


# ---------------------------------------------------------------------------
# utils.check_ignore
# ---------------------------------------------------------------------------

class TestCheckIgnore:
    def test_minigit_dir_always_ignored(self, repo):
        assert utils.check_ignore(".minigit/HEAD") is True

    def test_minigitignore_file_not_ignored_by_default(self, repo):
        # .minigitignore is a normal tracked file (like .gitignore in real git)
        assert utils.check_ignore(".minigitignore") is False

    def test_regular_file_not_ignored(self, repo):
        assert utils.check_ignore("regular.txt") is False

    def test_pattern_from_minigitignore_is_ignored(self, repo):
        (repo / ".minigitignore").write_text("*.log\n")
        assert utils.check_ignore("debug.log") is True

    def test_non_matching_file_not_ignored(self, repo):
        (repo / ".minigitignore").write_text("*.log\n")
        assert utils.check_ignore("important.txt") is False

    def test_directory_pattern_ignored(self, repo):
        (repo / ".minigitignore").write_text("build/\n")
        assert utils.check_ignore("build/output.js") is True

    def test_comment_line_in_minigitignore_not_treated_as_pattern(self, repo):
        (repo / ".minigitignore").write_text("# this is a comment\n")
        assert utils.check_ignore("this is a comment") is False


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_minigit_directory(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        assert (tmp_path / ".minigit").is_dir()

    def test_creates_required_subdirectories(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        assert (tmp_path / ".minigit" / "objects" / "commits").is_dir()
        assert (tmp_path / ".minigit" / "objects" / "blobs").is_dir()
        assert (tmp_path / ".minigit" / "refs" / "heads").is_dir()

    def test_creates_head_pointing_to_master(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        head = (tmp_path / ".minigit" / "HEAD").read_text()
        assert head == "ref: refs/heads/master"

    def test_creates_master_branch_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        assert (tmp_path / ".minigit" / "refs" / "heads" / "master").exists()

    def test_creates_empty_staging_area(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        with open(".minigit/index", "rb") as f:
            index = pickle.load(f)
        assert index == {"additions": {}, "removals": []}

    def test_creates_initial_commit(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert commit.message == "initial commit"
        assert commit.parent == []
        assert commit.files == {}

    def test_second_init_does_not_overwrite(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        main_commands.init()
        captured = capsys.readouterr()
        assert "already exists" in captured.out.lower()


# ---------------------------------------------------------------------------
# stage
# ---------------------------------------------------------------------------

class TestStage:
    def test_stage_addition_appears_in_index(self, repo):
        (repo / "file.txt").write_text("content")
        main_commands.stage(["file.txt"], "additions")
        _, additions, _ = utils.get_staging_area()
        assert "file.txt" in additions

    def test_staged_file_hash_matches_content(self, repo):
        (repo / "file.txt").write_bytes(b"content")
        main_commands.stage(["file.txt"], "additions")
        _, additions, _ = utils.get_staging_area()
        expected_hash = hashlib.sha1(b"content").hexdigest()
        assert additions["file.txt"] == expected_hash

    def test_stage_nonexistent_file_prints_error(self, repo, capsys):
        main_commands.stage(["ghost.txt"], "additions")
        captured = capsys.readouterr()
        assert "does not exist" in captured.out

    def test_stage_removal_of_untracked_file_prints_error(self, repo, capsys):
        (repo / "file.txt").write_text("content")
        main_commands.stage(["file.txt"], "removals")
        captured = capsys.readouterr()
        assert "cannot remove" in captured.out.lower()

    def test_stage_removal_of_tracked_file(self, repo_with_file):
        main_commands.stage(["hello.txt"], "removals")
        _, _, removals = utils.get_staging_area()
        assert "hello.txt" in removals

    def test_staging_addition_removes_from_removals(self, repo_with_file):
        main_commands.stage(["hello.txt"], "removals")
        (repo_with_file / "hello.txt").write_text("updated")
        main_commands.stage(["hello.txt"], "additions")
        _, _, removals = utils.get_staging_area()
        assert "hello.txt" not in removals

    def test_stage_directory_stages_all_files(self, repo):
        subdir = repo / "src"
        subdir.mkdir()
        (subdir / "a.py").write_text("a")
        (subdir / "b.py").write_text("b")
        main_commands.stage(["src"], "additions")
        _, additions, _ = utils.get_staging_area()
        assert any("a.py" in k for k in additions)
        assert any("b.py" in k for k in additions)


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------

class TestCommit:
    def test_commit_creates_commit_object(self, repo):
        (repo / "file.txt").write_text("hi")
        main_commands.stage(["file.txt"], "additions")
        main_commands.commit("my commit")
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert commit.message == "my commit"

    def test_commit_tracks_staged_files(self, repo):
        (repo / "file.txt").write_bytes(b"hi")
        main_commands.stage(["file.txt"], "additions")
        main_commands.commit("add file")
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert "file.txt" in commit.files

    def test_commit_has_correct_parent(self, repo):
        _, _, _, _, initial_hash = utils.check_head()
        (repo / "file.txt").write_text("hi")
        main_commands.stage(["file.txt"], "additions")
        main_commands.commit("second commit")
        _, _, _, _, new_hash = utils.check_head()
        new_commit = utils.get_commit(new_hash)
        assert new_commit.parent == [initial_hash]

    def test_commit_carries_over_unchanged_files(self, repo_with_file):
        (repo_with_file / "new.txt").write_text("new content")
        main_commands.stage(["new.txt"], "additions")
        main_commands.commit("second commit")
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert "hello.txt" in commit.files
        assert "new.txt" in commit.files

    def test_commit_removes_staged_removals(self, repo_with_file):
        main_commands.stage(["hello.txt"], "removals")
        main_commands.commit("remove file")
        basic_commands.empty()
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert "hello.txt" not in commit.files

    def test_branch_pointer_advances_after_commit(self, repo):
        _, _, _, _, initial_hash = utils.check_head()
        (repo / "file.txt").write_text("hi")
        main_commands.stage(["file.txt"], "additions")
        main_commands.commit("advance branch")
        _, _, _, _, new_hash = utils.check_head()
        assert new_hash != initial_hash


# ---------------------------------------------------------------------------
# empty / empty_file
# ---------------------------------------------------------------------------

class TestEmpty:
    def test_empty_clears_staging_area(self, repo):
        (repo / "file.txt").write_text("hi")
        main_commands.stage(["file.txt"], "additions")
        basic_commands.empty()
        _, additions, removals = utils.get_staging_area()
        assert additions == {}
        assert removals == []

    def test_empty_file_removes_specific_file(self, repo):
        (repo / "a.txt").write_text("a")
        (repo / "b.txt").write_text("b")
        main_commands.stage(["a.txt", "b.txt"], "additions")
        basic_commands.empty_file(["a.txt"])
        _, additions, _ = utils.get_staging_area()
        assert "a.txt" not in additions
        assert "b.txt" in additions

    def test_empty_file_not_in_staging_prints_error(self, repo, capsys):
        basic_commands.empty_file(["ghost.txt"])
        captured = capsys.readouterr()
        assert "cannot remove" in captured.out.lower()

    def test_empty_file_removes_from_removals(self, repo_with_file):
        main_commands.stage(["hello.txt"], "removals")
        basic_commands.empty_file(["hello.txt"])
        _, _, removals = utils.get_staging_area()
        assert "hello.txt" not in removals


# ---------------------------------------------------------------------------
# get_commit / CommitNotFoundError
# ---------------------------------------------------------------------------

class TestGetCommit:
    def test_get_commit_returns_commit_object(self, repo):
        _, _, _, _, head_hash = utils.check_head()
        commit = utils.get_commit(head_hash)
        assert isinstance(commit, Commit)

    def test_get_commit_raises_for_unknown_hash(self, repo):
        with pytest.raises(CommitNotFoundError):
            utils.get_commit("a" * 40)


# ---------------------------------------------------------------------------
# branch_create / branch_list / branch_delete / branch_switch
# ---------------------------------------------------------------------------

class TestBranch:
    def test_branch_create_makes_branch_file(self, repo):
        branch_commands.branch_create("feature")
        assert (repo / ".minigit" / "refs" / "heads" / "feature").exists()

    def test_branch_create_points_to_current_commit(self, repo):
        _, _, _, _, current_hash = utils.check_head()
        branch_commands.branch_create("feature")
        branch_hash = (repo / ".minigit" / "refs" / "heads" / "feature").read_text()
        assert branch_hash == current_hash

    def test_branch_list_outputs_branches(self, repo, capsys):
        branch_commands.branch_create("feature")
        # Switch back to master first so HEAD is attached
        with open(".minigit/HEAD", "w") as f:
            f.write("ref: refs/heads/master")
        branch_commands.branch_list()
        captured = capsys.readouterr()
        assert "master" in captured.out
        assert "feature" in captured.out

    def test_branch_delete_removes_branch_file(self, repo):
        branch_commands.branch_create("feature")
        # Detach HEAD so we can safely delete feature
        _, _, _, _, current_hash = utils.check_head()
        with open(".minigit/HEAD", "w") as f:
            f.write(current_hash)  # detach HEAD
        branch_commands.branch_delete(["feature"])
        assert not (repo / ".minigit" / "refs" / "heads" / "feature").exists()

    def test_branch_delete_current_branch_prints_error(self, repo, capsys):
        branch_commands.branch_delete(["master"])
        captured = capsys.readouterr()
        assert "cannot delete" in captured.out.lower()

    def test_branch_switch_updates_head(self, repo_with_file):
        branch_commands.branch_create("feature")
        # Go back to master
        with open(".minigit/HEAD", "w") as f:
            f.write("ref: refs/heads/master")
        branch_commands.branch_switch("feature")
        head_content = (repo_with_file / ".minigit" / "HEAD").read_text()
        assert "feature" in head_content

    def test_branch_switch_nonexistent_prints_error(self, repo, capsys):
        branch_commands.branch_switch("nonexistent")
        captured = capsys.readouterr()
        assert "does not seem to exist" in captured.out.lower()


# ---------------------------------------------------------------------------
# checkout_commit
# ---------------------------------------------------------------------------

class TestCheckoutCommit:
    def test_checkout_restores_file_content(self, repo):
        # Commit v1
        f = repo / "data.txt"
        f.write_bytes(b"version 1")
        main_commands.stage(["data.txt"], "additions")
        main_commands.commit("v1")
        basic_commands.empty()
        _, _, _, _, v1_hash = utils.check_head()

        # Commit v2
        f.write_bytes(b"version 2")
        main_commands.stage(["data.txt"], "additions")
        main_commands.commit("v2")
        basic_commands.empty()

        # Checkout v1
        branch_commands.checkout_commit(v1_hash)
        assert f.read_bytes() == b"version 1"

    def test_checkout_creates_detached_head(self, repo_with_file):
        _, _, _, _, commit_hash = utils.check_head()
        branch_commands.checkout_commit(commit_hash)
        head_content = (repo_with_file / ".minigit" / "HEAD").read_text()
        # Detached HEAD: content is just the hash, no "ref:"
        assert "refs" not in head_content

    def test_checkout_removes_file_not_in_target_commit(self, repo):
        # v1: no files beyond initial
        _, _, _, _, v1_hash = utils.check_head()

        # Add a file and commit as v2
        f = repo / "extra.txt"
        f.write_bytes(b"extra")
        main_commands.stage(["extra.txt"], "additions")
        main_commands.commit("add extra")
        basic_commands.empty()

        # Checkout back to v1 (initial commit has no files)
        branch_commands.checkout_commit(v1_hash)
        assert not f.exists()


# ---------------------------------------------------------------------------
# get_unstaged_tracked_modified
# ---------------------------------------------------------------------------

class TestGetUnstagedTrackedModified:
    def test_unmodified_file_classified_correctly(self, repo_with_file):
        # hello.txt was committed and not modified
        _, additions, removals = utils.get_staging_area()
        _, _, _, _, head_hash = utils.check_head()
        prev_files = utils.get_commit(head_hash).files
        directory_files = utils.get_directory_files_dictionary(".")
        unmodified, modified = utils.get_unstaged_tracked_modified(
            directory_files, additions, removals, prev_files
        )
        assert "hello.txt" in unmodified
        assert "hello.txt" not in modified

    def test_modified_file_classified_correctly(self, repo_with_file):
        # Modify hello.txt without staging
        (repo_with_file / "hello.txt").write_text("changed!")
        _, additions, removals = utils.get_staging_area()
        _, _, _, _, head_hash = utils.check_head()
        prev_files = utils.get_commit(head_hash).files
        directory_files = utils.get_directory_files_dictionary(".")
        unmodified, modified = utils.get_unstaged_tracked_modified(
            directory_files, additions, removals, prev_files
        )
        assert "hello.txt" in modified
        assert "hello.txt" not in unmodified


# ---------------------------------------------------------------------------
# merge (fast-forward and basic three-way)
# ---------------------------------------------------------------------------

class TestMerge:
    def test_fast_forward_merge_advances_branch(self, repo_with_file):
        # Create feature branch, add a commit on it
        _, _, _, _, base_hash = utils.check_head()
        branch_commands.branch_create("feature")

        (repo_with_file / "feature.txt").write_bytes(b"feature work")
        main_commands.stage(["feature.txt"], "additions")
        main_commands.commit("feature commit")
        basic_commands.empty()
        _, _, _, _, feature_hash = utils.check_head()

        # Switch back to master (which is still at base_hash)
        with open(".minigit/HEAD", "w") as f:
            f.write("ref: refs/heads/master")
        with open(".minigit/refs/heads/master", "w") as f:
            f.write(base_hash)

        # Fast-forward master into feature
        branch_commands.merge("feature", "ff merge")

        _, _, _, _, master_hash = utils.check_head()
        assert master_hash == feature_hash

    def test_same_tip_merge_returns_message(self, repo_with_file):
        branch_commands.branch_create("copy")
        result = branch_commands.merge("copy", "no-op")
        assert result is not None and "same" in result.lower()
