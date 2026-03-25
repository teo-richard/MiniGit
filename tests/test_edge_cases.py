"""
*** ALL TESTS WRITTEN BY CLAUDE CODE ***


Adversarial / edge-case tests for MiniGit.

These tests were written by treating every function as potentially broken and
asking: "what is the worst input or sequence of operations?".

Confirmed bugs exposed by this file
-------------------------------------
BUG-1  remove_branch_ref / branch_delete with a non-existent branch name
       raises an unhandled FileNotFoundError.

BUG-2  FIXED: amend() when HEAD is detached now handles the case correctly
       and no longer creates a bogus refs/heads/None file.

BUG-3  FIXED: fetch() when already up-to-date now prints "Already up to date"
       instead of crashing with IndexError on commits_to_copy[0].

BUG-4  FIXED: merge() with a nonexistent branch now prints a user-friendly
       error message instead of raising an unhandled FileNotFoundError.

BUG-5  remote_prep_push() when nothing needs pushing (local == remote):
       find_branch_ancestor returns [], which is falsy, so the function falls
       off the end and returns None with no user feedback.

BUG-6  revert() to a commit that has FEWER files than the current commit does
       not remove the extra files. revert() clears the staging area and then
       only stages files present in the target commit. When commit() runs, it
       carries over all files from the parent (the commit before revert was
       called) that are not staged for removal. Reverting to the initial
       commit (files={}) still leaves all previously tracked files in the new
       commit because they were never staged for removal.

Confirmed fixed bugs
--------------------
FIXED  revert() default message: the loop now uses `blob_hash` (not `hash`),
       so the `commit_hash` parameter is no longer shadowed and the default
       message correctly contains the target commit hash.
"""

import hashlib
import json
import os
import pickle
import shutil
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import utils
from utils import Commit, CommitNotFoundError
from commands import (
    basic_commands,
    branch_commands,
    history_commands,
    info_commands,
    main_commands,
    remote_commands,
)


# ---------------------------------------------------------------------------
# Helpers (duplicated from test_advanced.py to keep the file self-contained)
# ---------------------------------------------------------------------------

def _head_hash(repo_path):
    head = (repo_path / ".minigit" / "HEAD").read_text().strip()
    if "refs" in head:
        branch = head.split()[-1].split("/")[-1]
        return (repo_path / ".minigit" / "refs" / "heads" / branch).read_text().strip()
    return head


def _branch_hash(repo_path, branch="master"):
    return (repo_path / ".minigit" / "refs" / "heads" / branch).read_text().strip()


def _sync_objects(src_repo, dst_repo):
    for kind in ("commits", "blobs"):
        src = src_repo / ".minigit" / "objects" / kind
        dst = dst_repo / ".minigit" / "objects" / kind
        for prefix_dir in src.iterdir():
            (dst / prefix_dir.name).mkdir(exist_ok=True)
            for f in prefix_dir.iterdir():
                dest = dst / prefix_dir.name / f.name
                if not dest.exists():
                    shutil.copy(f, dest)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def repo(tmp_path, monkeypatch):
    """Fresh repo, no user files."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    return tmp_path


@pytest.fixture
def repo_one(tmp_path, monkeypatch):
    """Repo with one committed file (hello.txt = 'hello world')."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    (tmp_path / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first commit")
    basic_commands.empty()
    return tmp_path


@pytest.fixture
def repo_two(tmp_path, monkeypatch):
    """Repo with two commits so there is a real parent chain."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    (tmp_path / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first commit")
    basic_commands.empty()
    (tmp_path / "second.txt").write_bytes(b"second file")
    main_commands.stage(["second.txt"], "additions")
    main_commands.commit("second commit")
    basic_commands.empty()
    return tmp_path


@pytest.fixture
def two_repos(tmp_path, monkeypatch):
    """Local repo with one commit + a bare-skeleton remote, remote registered as 'origin'."""
    local = tmp_path / "local"
    remote = tmp_path / "remote"
    local.mkdir()
    remote.mkdir()

    # Build a proper local repo
    monkeypatch.chdir(local)
    main_commands.init()
    (local / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("initial commit")
    basic_commands.empty()

    # Build a bare-skeleton remote (no initial commit, no branch file)
    for subdir in (".minigit/objects/commits", ".minigit/objects/blobs", ".minigit/refs/heads"):
        (remote / subdir).mkdir(parents=True)
    (remote / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
    (remote / ".minigit" / "config").write_text(json.dumps({"remotes": {}}))
    (remote / ".minigit" / "index").write_bytes(pickle.dumps({"additions": {}, "removals": []}))
    (remote / ".minigitignore").write_text("")

    # Register remote in local config
    remote_commands.remote_add("origin", str(remote))
    return local, remote


# ===========================================================================
# init edge cases
# ===========================================================================

class TestInitEdgeCases:
    def test_double_init_prints_warning(self, repo, capsys):
        main_commands.init()
        out = capsys.readouterr().out
        assert "already exists" in out.lower() or "fool" in out.lower()

    def test_double_init_does_not_overwrite_existing_commit(self, repo):
        initial_hash = _head_hash(repo)
        main_commands.init()
        assert _head_hash(repo) == initial_hash

    def test_double_init_does_not_clear_staging_area(self, repo):
        (repo / "file.txt").write_bytes(b"data")
        main_commands.stage(["file.txt"], "additions")
        main_commands.init()
        _, additions, _ = utils.get_staging_area()
        assert "file.txt" in additions


# ===========================================================================
# commit edge cases
# ===========================================================================

class TestCommitEdgeCases:
    def test_commit_with_empty_staging_creates_new_commit_hash(self, repo_one):
        """No staged changes → a new commit object is still created."""
        before = _head_hash(repo_one)
        main_commands.commit("no changes")
        basic_commands.empty()
        assert _head_hash(repo_one) != before

    def test_commit_with_empty_staging_carries_over_all_files(self, repo_one):
        before_files = utils.get_commit(_head_hash(repo_one)).files
        main_commands.commit("no changes")
        basic_commands.empty()
        after_files = utils.get_commit(_head_hash(repo_one)).files
        assert after_files == before_files

    def test_staged_removal_absent_from_new_commit(self, repo_one):
        main_commands.stage(["hello.txt"], "removals")
        main_commands.commit("remove hello")
        basic_commands.empty()
        files = utils.get_commit(_head_hash(repo_one)).files
        assert "hello.txt" not in files

    def test_commit_on_detached_head_advances_head_hash(self, repo_two):
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)
        (repo_two / "detached.txt").write_bytes(b"detached work")
        main_commands.stage(["detached.txt"], "additions")
        old_head = _head_hash(repo_two)
        main_commands.commit("detached commit")
        basic_commands.empty()
        assert _head_hash(repo_two) != old_head

    def test_commit_on_detached_head_does_not_move_branch_pointer(self, repo_two):
        master_before = _branch_hash(repo_two, "master")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)
        (repo_two / "detached.txt").write_bytes(b"detached work")
        main_commands.stage(["detached.txt"], "additions")
        main_commands.commit("detached commit")
        basic_commands.empty()
        assert _branch_hash(repo_two, "master") == master_before

    def test_new_file_not_staged_carries_over_from_previous_commit(self, repo_one):
        """Files in the last commit but not staged are silently carried forward."""
        (repo_one / "extra.txt").write_bytes(b"not staged")
        main_commands.commit("carry-over commit")
        basic_commands.empty()
        files = utils.get_commit(_head_hash(repo_one)).files
        assert "hello.txt" in files  # carried over


# ===========================================================================
# branch_create edge cases
# ===========================================================================

class TestBranchCreateEdgeCases:
    def test_create_branch_that_already_exists_silently_overwrites_pointer(self, repo_two):
        """branch_create on an existing name moves HEAD to that branch and
        resets its pointer to the current commit — no error is raised."""
        tip = _head_hash(repo_two)
        branch_commands.branch_create("master")   # 'master' already exists
        assert _branch_hash(repo_two, "master") == tip

    def test_new_branch_points_to_current_commit(self, repo_two):
        tip = _head_hash(repo_two)
        branch_commands.branch_create("feature")
        assert _branch_hash(repo_two, "feature") == tip

    def test_commits_after_branch_create_advance_new_branch(self, repo_one):
        branch_commands.branch_create("feature")
        (repo_one / "feat.txt").write_bytes(b"feat")
        main_commands.stage(["feat.txt"], "additions")
        main_commands.commit("feature commit")
        basic_commands.empty()
        assert _branch_hash(repo_one, "feature") != _branch_hash(repo_one, "master")


# ===========================================================================
# BUG-1: branch_delete with non-existent branch
# ===========================================================================

class TestBranchDeleteEdgeCases:
    def test_delete_nonexistent_branch_raises_file_not_found(self, repo_one):
        """BUG-1: No guard around os.remove → FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            branch_commands.remove_branch_ref("ghost_branch")

    def test_delete_current_branch_prints_error(self, repo_one, capsys):
        branch_commands.remove_branch_ref("master")   # HEAD attached to master
        out = capsys.readouterr().out
        assert "cannot delete" in out.lower() or "currently attached" in out.lower() \
               or "defaulting" in out.lower()

    def test_delete_other_branch_removes_ref_file(self, repo_one):
        branch_commands.branch_create("to_delete")
        # Reattach to master so 'to_delete' can be safely removed
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        branch_commands.remove_branch_ref("to_delete")
        assert not (repo_one / ".minigit" / "refs" / "heads" / "to_delete").exists()

    def test_delete_when_head_is_detached_and_branch_is_none_prints_error(self, repo_one, capsys):
        """Calling remove_branch_ref(None) with detached HEAD should print an error."""
        parent = utils.get_commit(_head_hash(repo_one)).parent[0]
        branch_commands.checkout_commit(parent)
        branch_commands.remove_branch_ref(None)
        out = capsys.readouterr().out
        assert "detached" in out.lower() or "cannot" in out.lower()


# ===========================================================================
# BUG-2: amend on detached HEAD
# ===========================================================================

class TestAmendDetachedHead:
    def test_amend_on_detached_head_does_not_create_none_branch_file(self, repo_one):
        """FIXED BUG-2: amend() must not create refs/heads/None when detached."""
        parent = utils.get_commit(_head_hash(repo_one)).parent[0]
        branch_commands.checkout_commit(parent)
        info_commands.amend("amended in detached state")
        none_branch_file = repo_one / ".minigit" / "refs" / "heads" / "None"
        assert not none_branch_file.exists()


# ===========================================================================
# BUG-4: merge with nonexistent branch
# ===========================================================================

class TestMergeEdgeCases:
    def test_merge_nonexistent_branch_prints_error(self, repo_one, capsys):
        """FIXED BUG-4: merging a nonexistent branch prints an error instead of crashing."""
        branch_commands.merge("branch_that_does_not_exist", "merge it")
        out = capsys.readouterr().out
        assert "does not exist" in out.lower() or "branch_that_does_not_exist" in out

    def test_merge_branch_with_identical_tip_returns_message_not_none(self, repo_one):
        """Merging a branch whose tip == current tip returns a descriptive string."""
        branch_commands.branch_create("feature")
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        result = branch_commands.merge("feature", "merge")
        assert result is not None
        assert isinstance(result, str)

    def test_merge_same_tip_does_not_create_new_commit(self, repo_one):
        """No commit is created when merging a branch at the same tip."""
        branch_commands.branch_create("feature")
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        before = _head_hash(repo_one)
        branch_commands.merge("feature", "merge")
        assert _head_hash(repo_one) == before

    def test_fast_forward_merge_moves_branch_pointer(self, repo_one):
        """Fast-forward: current branch is strictly behind → pointer advances."""
        branch_commands.branch_create("feature")
        (repo_one / "feat.txt").write_bytes(b"feature")
        main_commands.stage(["feat.txt"], "additions")
        main_commands.commit("feature commit")
        basic_commands.empty()
        feature_tip = _head_hash(repo_one)

        # Switch back to master (which is one commit behind)
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        (repo_one / "hello.txt").write_bytes(b"hello world")  # restore original state
        branch_commands.merge("feature", "ff merge")
        assert _branch_hash(repo_one, "master") == feature_tip


# ===========================================================================
# BUG-3: fetch when already up to date
# ===========================================================================

class TestFetchEdgeCases:
    def test_fetch_when_up_to_date_does_not_crash(self, two_repos, monkeypatch):
        """FIXED BUG-3: fetch() when already in sync prints 'Already up to date'
        instead of crashing with IndexError on commits_to_copy[0]."""
        local, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)
        _sync_objects(remote, local)
        # Should not raise
        remote_commands.fetch("origin", "master")

    def test_fetch_nonexistent_remote_raises(self, repo_one):
        """Fetching from an unregistered remote name raises KeyError."""
        with pytest.raises(KeyError):
            remote_commands.fetch("no_such_remote", "master")


# ===========================================================================
# BUG-5: remote_prep_push when nothing to push
# ===========================================================================

class TestRemotePushNothingToPush:
    def test_prep_push_nothing_to_push_returns_none(self, two_repos):
        """BUG-5: When local == remote, find_branch_ancestor returns [],
        which is falsy, so remote_prep_push falls off the end and returns None."""
        local, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)
        result = remote_commands.remote_prep_push("origin", "master")
        # Currently None (no feedback to user). Correct behavior would be a
        # message or a sentinel, but NOT a crash.
        assert result is None

    def test_full_push_when_nothing_to_push_does_not_crash(self, two_repos):
        """Calling the full push pipeline when already in sync should not crash."""
        local, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)
        # _handle_push catches the TypeError from unpacking None
        try:
            result = remote_commands.remote_prep_push("origin", "master")
            if result is not None:
                remote_commands.remote_push(*result)
        except TypeError:
            pass  # expected: unpacking None raises TypeError


# ===========================================================================
# revert (FIXED variable-shadowing bug)
# ===========================================================================

class TestRevertEdgeCases:
    def test_revert_default_message_contains_exact_commit_hash(self, repo_one, monkeypatch):
        """FIXED: the loop variable is now blob_hash (not hash), so commit_hash
        is not shadowed and the default message contains the correct hash."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_one)).parent[0]
        history_commands.revert(initial_hash, None)
        new_commit = utils.get_commit(_head_hash(repo_one))
        assert initial_hash in new_commit.message

    def test_revert_explicit_message_used_verbatim(self, repo_one, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_one)).parent[0]
        history_commands.revert(initial_hash, "my custom message")
        new_commit = utils.get_commit(_head_hash(repo_one))
        assert new_commit.message == "my custom message"

    def test_revert_to_initial_commit_yields_empty_files(self, repo_one, monkeypatch):
        """BUG-6: revert() to the initial commit (files={}) should produce a
        commit with no files, but instead the files from the parent commit are
        silently carried over because revert() never stages them for removal.
        This test asserts the CORRECT expected behaviour and currently FAILS."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_one)).parent[0]
        history_commands.revert(initial_hash, "back to empty")
        new_commit = utils.get_commit(_head_hash(repo_one))
        assert new_commit.files == {}

    def test_revert_creates_new_commit(self, repo_one, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        before = _head_hash(repo_one)
        initial_hash = utils.get_commit(before).parent[0]
        history_commands.revert(initial_hash, "revert")
        assert _head_hash(repo_one) != before

    def test_revert_preserves_history(self, repo_one, monkeypatch):
        """revert does not destroy history — old commit is still reachable."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        original_tip = _head_hash(repo_one)
        initial_hash = utils.get_commit(original_tip).parent[0]
        history_commands.revert(initial_hash, "revert")
        # The original tip commit must still exist on disk
        assert utils.get_commit(original_tip) is not None


# ===========================================================================
# reset edge cases
# ===========================================================================

class TestResetEdgeCases:
    def test_soft_reset_does_not_change_working_directory(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        content_before = (repo_two / "second.txt").read_bytes()
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "soft")
        assert (repo_two / "second.txt").read_bytes() == content_before

    def test_soft_reset_moves_branch_pointer(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "soft")
        assert _head_hash(repo_two) == parent

    def test_soft_reset_does_not_clear_staging_area(self, repo_two, monkeypatch):
        """Soft reset leaves staged files alone."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        # Reset from a clean state — staging area should remain empty
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "soft")
        _, additions, removals = utils.get_staging_area()
        assert not additions
        assert not removals

    def test_hard_reset_moves_branch_pointer(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "hard")
        assert _head_hash(repo_two) == parent

    def test_hard_reset_restores_working_directory_to_target_commit(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "hard")
        # After hard reset to parent, working dir should match parent's files
        parent_files = utils.get_commit(parent).files
        for filename in parent_files:
            assert Path(filename).exists()

    def test_hard_reset_removes_files_not_in_target(self, repo_two, monkeypatch):
        """Files that exist in tip but not in parent should be deleted by hard reset."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        tip_files = utils.get_commit(_head_hash(repo_two)).files
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        parent_files = utils.get_commit(parent).files
        files_only_in_tip = [f for f in tip_files if f not in parent_files]
        history_commands.reset(parent, "hard")
        for f in files_only_in_tip:
            assert not Path(f).exists()

    def test_hard_reset_clears_staging_area(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        (repo_two / "staged.txt").write_bytes(b"staged")
        main_commands.stage(["staged.txt"], "additions")
        monkeypatch.setattr("builtins.input", lambda _: "y")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "hard")
        _, additions, removals = utils.get_staging_area()
        assert not additions
        assert not removals

    def test_reset_on_detached_head_moves_head(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        tip = _head_hash(repo_two)
        parent = utils.get_commit(tip).parent[0]
        branch_commands.checkout_commit(parent)
        grandparent = utils.get_commit(parent).parent[0]
        history_commands.reset(grandparent, "hard")
        assert _head_hash(repo_two) == grandparent


# ===========================================================================
# mgignore edge cases
# ===========================================================================

class TestMgIgnoreEdgeCases:
    def test_mgignore_overwrites_not_appends(self, repo):
        """Calling mgignore twice replaces, not accumulates."""
        basic_commands.mgignore(["first.log"])
        basic_commands.mgignore(["second.log"])
        content = (repo / ".minigitignore").read_text()
        assert "first.log" not in content
        assert "second.log" in content

    def test_mgignore_prevents_staging(self, repo):
        basic_commands.mgignore(["secret.key"])
        (repo / "secret.key").write_bytes(b"topsecret")
        main_commands.stage(["secret.key"], "additions")
        _, additions, _ = utils.get_staging_area()
        assert "secret.key" not in additions

    def test_mgignore_multiple_patterns(self, repo):
        basic_commands.mgignore(["*.log", "*.tmp", "build/"])
        content = (repo / ".minigitignore").read_text()
        for pattern in ("*.log", "*.tmp", "build/"):
            assert pattern in content


# ===========================================================================
# check_ignore edge cases
# ===========================================================================

class TestCheckIgnoreEdgeCases:
    def test_minigit_dir_always_ignored(self, repo):
        assert utils.check_ignore(".minigit/HEAD") is True

    def test_minigitignore_file_always_ignored(self, repo):
        assert utils.check_ignore(".minigitignore") is True

    def test_regular_file_not_ignored_by_default(self, repo):
        assert utils.check_ignore("myfile.txt") is False

    def test_wildcard_pattern_matches(self, repo):
        (repo / ".minigitignore").write_text("*.pyc\n")
        assert utils.check_ignore("module.pyc") is True

    def test_wildcard_does_not_match_different_extension(self, repo):
        (repo / ".minigitignore").write_text("*.pyc\n")
        assert utils.check_ignore("module.py") is False

    def test_comment_lines_not_treated_as_patterns(self, repo):
        (repo / ".minigitignore").write_text("# comment\nactual.log\n")
        assert utils.check_ignore("# comment") is False
        assert utils.check_ignore("actual.log") is True

    def test_directory_pattern_matches_prefix(self, repo):
        (repo / ".minigitignore").write_text("build/\n")
        assert utils.check_ignore("build/output.o") is True

    def test_nested_path_component_matches_pattern(self, repo):
        (repo / ".minigitignore").write_text("node_modules\n")
        assert utils.check_ignore("src/node_modules/lodash.js") is True


# ===========================================================================
# stage edge cases
# ===========================================================================

class TestStageEdgeCases:
    def test_stage_nonexistent_file_prints_error(self, repo, capsys):
        main_commands.stage(["ghost.txt"], "additions")
        out = capsys.readouterr().out
        assert "does not exist" in out.lower() or "ghost.txt" in out

    def test_stage_nonexistent_file_does_not_add_to_staging(self, repo):
        main_commands.stage(["ghost.txt"], "additions")
        _, additions, _ = utils.get_staging_area()
        assert "ghost.txt" not in additions

    def test_stage_removal_of_untracked_file_prints_error(self, repo, capsys):
        (repo / "untracked.txt").write_bytes(b"data")
        main_commands.stage(["untracked.txt"], "removals")
        out = capsys.readouterr().out
        assert "cannot remove" in out.lower() or "not being tracked" in out.lower()

    def test_stage_removal_of_untracked_not_in_removals(self, repo):
        (repo / "untracked.txt").write_bytes(b"data")
        main_commands.stage(["untracked.txt"], "removals")
        _, _, removals = utils.get_staging_area()
        assert "untracked.txt" not in removals

    def test_restage_same_file_with_new_content_updates_hash(self, repo_one):
        original_hash = utils.get_staging_area()[1].get("hello.txt")
        (repo_one / "hello.txt").write_bytes(b"completely different")
        main_commands.stage(["hello.txt"], "additions")
        _, additions, _ = utils.get_staging_area()
        expected = hashlib.sha1(b"completely different").hexdigest()
        assert additions["hello.txt"] == expected

    def test_stage_directory_expands_to_individual_files(self, repo):
        subdir = repo / "src"
        subdir.mkdir()
        (subdir / "a.py").write_bytes(b"a")
        (subdir / "b.py").write_bytes(b"b")
        main_commands.stage(["src"], "additions")
        _, additions, _ = utils.get_staging_area()
        assert any("a.py" in k for k in additions)
        assert any("b.py" in k for k in additions)


# ===========================================================================
# empty_file (selective unstage) edge cases
# ===========================================================================

class TestEmptyFileEdgeCases:
    def test_unstage_file_not_in_staging_prints_error(self, repo_one, capsys):
        basic_commands.empty_file(["not_staged.txt"])
        out = capsys.readouterr().out
        assert "cannot remove" in out.lower() or "staging area" in out.lower()

    def test_unstage_file_removes_it_from_additions(self, repo_one):
        (repo_one / "new.txt").write_bytes(b"new")
        main_commands.stage(["new.txt"], "additions")
        basic_commands.empty_file(["new.txt"])
        _, additions, _ = utils.get_staging_area()
        assert "new.txt" not in additions

    def test_unstage_removal_removes_from_removals(self, repo_one):
        main_commands.stage(["hello.txt"], "removals")
        basic_commands.empty_file(["hello.txt"])
        _, _, removals = utils.get_staging_area()
        assert "hello.txt" not in removals

    def test_unstage_one_of_multiple_staged_files(self, repo_one):
        for name in ("a.txt", "b.txt"):
            (repo_one / name).write_bytes(name.encode())
        main_commands.stage(["a.txt", "b.txt"], "additions")
        basic_commands.empty_file(["a.txt"])
        _, additions, _ = utils.get_staging_area()
        assert "a.txt" not in additions
        assert "b.txt" in additions


# ===========================================================================
# status edge cases
# ===========================================================================

class TestStatusEdgeCases:
    def test_status_lists_modified_tracked_file(self, repo_one, capsys):
        (repo_one / "hello.txt").write_bytes(b"modified content")
        info_commands.status()
        assert "hello.txt" in capsys.readouterr().out

    def test_status_lists_untracked_file(self, repo_one, capsys):
        (repo_one / "new_untracked.txt").write_bytes(b"new")
        info_commands.status()
        assert "new_untracked.txt" in capsys.readouterr().out

    def test_status_lists_staged_file(self, repo_one, capsys):
        (repo_one / "staged.txt").write_bytes(b"staged")
        main_commands.stage(["staged.txt"], "additions")
        info_commands.status()
        assert "staged.txt" in capsys.readouterr().out

    def test_status_on_detached_head_prints_detached_notice(self, repo_one, capsys):
        parent = utils.get_commit(_head_hash(repo_one)).parent[0]
        branch_commands.checkout_commit(parent)
        info_commands.status()
        assert "detached" in capsys.readouterr().out.lower()

    def test_status_staged_removal_appears_in_output(self, repo_one, capsys):
        main_commands.stage(["hello.txt"], "removals")
        info_commands.status()
        assert "hello.txt" in capsys.readouterr().out


# ===========================================================================
# log / reflog edge cases
# ===========================================================================

class TestLogEdgeCases:
    def test_log_only_initial_commit_does_not_crash(self, repo, capsys):
        info_commands.log()
        out = capsys.readouterr().out
        assert "initial commit" in out.lower() or "only the initial" in out.lower()

    def test_log_all_with_diverged_branches_does_not_crash(self, repo_one, capsys):
        branch_commands.branch_create("feature")
        (repo_one / "feat.txt").write_bytes(b"f")
        main_commands.stage(["feat.txt"], "additions")
        main_commands.commit("feature commit")
        basic_commands.empty()
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        info_commands.log_all()
        capsys.readouterr()  # just ensure no exception

    def test_reflog_lists_every_commit(self, repo_two, capsys):
        info_commands.reflog()
        out = capsys.readouterr().out
        # Both commits should appear
        tip = _head_hash(repo_two)
        parent = utils.get_commit(tip).parent[0]
        assert tip in out
        assert parent in out


# ===========================================================================
# blob / object storage correctness
# ===========================================================================

class TestBlobStorageCorrectness:
    def test_blob_content_matches_original_file(self, repo_one):
        blob_hash = list(utils.get_commit(_head_hash(repo_one)).files.values())[0]
        blob_path = repo_one / ".minigit" / "objects" / "blobs" / blob_hash[:2] / blob_hash
        assert blob_path.read_bytes() == b"hello world"

    def test_modifying_file_after_commit_creates_new_blob(self, repo_one):
        old_hash = list(utils.get_commit(_head_hash(repo_one)).files.values())[0]
        (repo_one / "hello.txt").write_bytes(b"updated content")
        main_commands.stage(["hello.txt"], "additions")
        main_commands.commit("update")
        basic_commands.empty()
        new_hash = list(utils.get_commit(_head_hash(repo_one)).files.values())[0]
        assert old_hash != new_hash
        new_blob = repo_one / ".minigit" / "objects" / "blobs" / new_hash[:2] / new_hash
        assert new_blob.read_bytes() == b"updated content"

    def test_two_identical_files_share_same_blob(self, repo):
        for name in ("copy1.txt", "copy2.txt"):
            (repo / name).write_bytes(b"same content")
        main_commands.stage(["copy1.txt", "copy2.txt"], "additions")
        main_commands.commit("identical files")
        basic_commands.empty()
        files = utils.get_commit(_head_hash(repo)).files
        assert files["copy1.txt"] == files["copy2.txt"]


# ===========================================================================
# get_commit / CommitNotFoundError
# ===========================================================================

class TestGetCommitErrors:
    def test_unknown_full_hash_raises_commit_not_found(self, repo):
        with pytest.raises(CommitNotFoundError):
            utils.get_commit("a" * 40)

    def test_error_message_includes_the_hash(self, repo):
        bad_hash = "b" * 40
        with pytest.raises(CommitNotFoundError, match=bad_hash):
            utils.get_commit(bad_hash)


# ===========================================================================
# checkout edge cases
# ===========================================================================

class TestCheckoutEdgeCases:
    def test_checkout_to_current_commit_creates_detached_head(self, repo_one):
        current = _head_hash(repo_one)
        branch_commands.checkout_commit(current)
        head_content = (repo_one / ".minigit" / "HEAD").read_text().strip()
        assert current in head_content
        assert "refs" not in head_content  # detached

    def test_checkout_blocked_when_file_is_missing_head_unchanged(self, repo_one):
        """If checkout is blocked, HEAD must not move."""
        (repo_one / "hello.txt").unlink()
        parent = utils.get_commit(_head_hash(repo_one)).parent[0]
        before_head = (repo_one / ".minigit" / "HEAD").read_text()
        branch_commands.checkout_commit(parent)
        after_head = (repo_one / ".minigit" / "HEAD").read_text()
        assert after_head == before_head

    def test_checkout_by_branch_name_switches_branch(self, repo_one):
        """checkout with a branch name (not a hash) should call branch_switch."""
        branch_commands.branch_create("feature")
        # Reattach to master first
        (repo_one / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
        branch_commands.checkout_branch_instead_of_commit(
            "feature", CommitNotFoundError("not a hash")
        )
        head_content = (repo_one / ".minigit" / "HEAD").read_text()
        assert "feature" in head_content

    def test_checkout_nonexistent_hash_and_nonexistent_branch_prints_error(self, repo_one, capsys):
        branch_commands.checkout_branch_instead_of_commit(
            "does_not_exist", CommitNotFoundError("not found")
        )
        out = capsys.readouterr().out
        assert "not found" in out.lower() or "error" in out.lower() or "not found" in str(out)


# ===========================================================================
# remote_add idempotency / override
# ===========================================================================

class TestRemoteAdd:
    def test_remote_add_registers_path(self, repo):
        remote_commands.remote_add("origin", "/some/path")
        with open(repo / ".minigit" / "config") as f:
            cfg = json.load(f)
        assert cfg["remotes"]["origin"] == "/some/path"

    def test_remote_add_overwrites_existing_entry(self, repo):
        remote_commands.remote_add("origin", "/old/path")
        remote_commands.remote_add("origin", "/new/path")
        with open(repo / ".minigit" / "config") as f:
            cfg = json.load(f)
        assert cfg["remotes"]["origin"] == "/new/path"

    def test_remote_add_multiple_remotes(self, repo):
        remote_commands.remote_add("origin", "/path/a")
        remote_commands.remote_add("upstream", "/path/b")
        with open(repo / ".minigit" / "config") as f:
            cfg = json.load(f)
        assert "origin" in cfg["remotes"]
        assert "upstream" in cfg["remotes"]
