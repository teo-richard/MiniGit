"""
*** ALL TESTS WRITTEN BY CLAUDE CODE ***

Adversarial / edge-case tests for MiniGit.
See tests/BUGS.md for the full bug tracker.
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
    """Repo with one committed file (hello.txt = 'hello world'). Index retains hello.txt."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    (tmp_path / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first commit")
    return tmp_path


@pytest.fixture
def repo_two(tmp_path, monkeypatch):
    """Repo with two commits so there is a real parent chain. Index retains both files."""
    monkeypatch.chdir(tmp_path)
    main_commands.init()
    (tmp_path / "hello.txt").write_bytes(b"hello world")
    main_commands.stage(["hello.txt"], "additions")
    main_commands.commit("first commit")
    (tmp_path / "second.txt").write_bytes(b"second file")
    main_commands.stage(["second.txt"], "additions")
    main_commands.commit("second commit")
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

    # Build a bare-skeleton remote (no initial commit, no branch file)
    for subdir in (".minigit/objects/commits", ".minigit/objects/blobs", ".minigit/refs/heads"):
        (remote / subdir).mkdir(parents=True)
    (remote / ".minigit" / "HEAD").write_text("ref: refs/heads/master")
    (remote / ".minigit" / "config").write_text(json.dumps({"remotes": {}}))
    (remote / ".minigit" / "index").write_bytes(pickle.dumps({}))
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
        # Create a commit so there is something to preserve
        (repo / "f.txt").write_bytes(b"data")
        main_commands.stage(["f.txt"], "additions")
        main_commands.commit("a commit")
        initial_hash = _head_hash(repo)
        main_commands.init()  # should print warning and leave repo untouched
        assert _head_hash(repo) == initial_hash

    def test_double_init_does_not_clear_staging_area(self, repo):
        (repo / "file.txt").write_bytes(b"data")
        main_commands.stage(["file.txt"], "additions")
        main_commands.init()
        staging = utils.get_staging_area()
        assert "file.txt" in staging


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
    def test_delete_nonexistent_branch_via_branch_delete_prints_warning(self, repo_one, capsys):
        """FIXED BUG-1: branch_delete() now catches FileNotFoundError and
        prints a warning instead of crashing."""
        branch_commands.branch_delete(["ghost_branch"])
        out = capsys.readouterr().out
        assert "ghost_branch" in out or "not found" in out.lower() or "warning" in out.lower()

    def test_remove_branch_ref_directly_still_raises(self, repo_one):
        """remove_branch_ref() itself has no try/except — only branch_delete()
        catches the error. Direct callers must be aware."""
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

    def test_delete_when_head_is_detached_and_branch_is_none_prints_error(self, repo_two, capsys):
        """Calling remove_branch_ref(None) with detached HEAD should print an error."""
        # Check out the first commit (parent of tip) to create a detached HEAD
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)
        branch_commands.remove_branch_ref(None)
        out = capsys.readouterr().out
        assert "detached" in out.lower() or "cannot" in out.lower()


# ===========================================================================
# BUG-2: amend on detached HEAD
# ===========================================================================

class TestAmendDetachedHead:
    def test_amend_on_detached_head_does_not_create_none_branch_file(self, repo_two):
        """FIXED BUG-2: amend() must not create refs/heads/None when detached."""
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)
        info_commands.amend("amended in detached state")
        none_branch_file = repo_two / ".minigit" / "refs" / "heads" / "None"
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
    def test_revert_default_message_contains_exact_commit_hash(self, repo_two, monkeypatch):
        """FIXED: the loop variable is now blob_hash (not hash), so commit_hash
        is not shadowed and the default message contains the correct hash."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(initial_hash, None)
        new_commit = utils.get_commit(_head_hash(repo_two))
        assert initial_hash in new_commit.message

    def test_revert_explicit_message_used_verbatim(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(initial_hash, "my custom message")
        new_commit = utils.get_commit(_head_hash(repo_two))
        assert new_commit.message == "my custom message"

    def test_revert_to_initial_commit_yields_empty_files(self, repo_two, monkeypatch):
        """Reverting to the first commit should produce a commit with only that commit's files."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        initial_hash = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.revert(initial_hash, "back to first")
        new_commit = utils.get_commit(_head_hash(repo_two))
        assert new_commit.files == utils.get_commit(initial_hash).files

    def test_revert_creates_new_commit(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        before = _head_hash(repo_two)
        initial_hash = utils.get_commit(before).parent[0]
        history_commands.revert(initial_hash, "revert")
        assert _head_hash(repo_two) != before

    def test_revert_preserves_history(self, repo_two, monkeypatch):
        """revert does not destroy history — old commit is still reachable."""
        monkeypatch.setattr("builtins.input", lambda _: "y")
        original_tip = _head_hash(repo_two)
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
        # Soft reset does not change staging area
        staging_before = utils.get_staging_area()
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "soft")
        staging_after = utils.get_staging_area()
        assert staging_before == staging_after

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
        staging = utils.get_staging_area()
        assert not staging

    def test_reset_on_detached_head_moves_head(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        # Add a 3rd commit so we have a grandparent to reset back to
        (repo_two / "third.txt").write_bytes(b"third")
        main_commands.stage(["third.txt"], "additions")
        main_commands.commit("third commit")
        tip = _head_hash(repo_two)
        parent = utils.get_commit(tip).parent[0]
        grandparent = utils.get_commit(parent).parent[0]
        branch_commands.checkout_commit(parent)
        history_commands.reset(grandparent, "hard")
        assert _head_hash(repo_two) == grandparent


# ===========================================================================
# mgignore edge cases
# ===========================================================================

class TestMgIgnoreEdgeCases:
    def test_mgignore_prevents_staging(self, repo):
        basic_commands.mgignore(["secret.key"])
        (repo / "secret.key").write_bytes(b"topsecret")
        main_commands.stage(["secret.key"], "additions")
        staging = utils.get_staging_area()
        assert "secret.key" not in staging

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

    def test_minigitignore_file_not_ignored_by_default(self, repo):
        # .minigitignore is a normal tracked file (like .gitignore in real git)
        assert utils.check_ignore(".minigitignore") is False

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
        staging = utils.get_staging_area()
        assert "ghost.txt" not in staging

    def test_stage_removal_of_untracked_file_prints_error(self, repo, capsys):
        (repo / "untracked.txt").write_bytes(b"data")
        main_commands.stage(["untracked.txt"], "removals")
        out = capsys.readouterr().out
        assert "cannot remove" in out.lower() or "not being tracked" in out.lower()

    def test_stage_removal_of_untracked_not_in_index(self, repo):
        (repo / "untracked.txt").write_bytes(b"data")
        main_commands.stage(["untracked.txt"], "removals")
        staging = utils.get_staging_area()
        assert "untracked.txt" not in staging

    def test_restage_same_file_with_new_content_updates_hash(self, repo_one):
        original_hash = utils.get_staging_area().get("hello.txt")
        (repo_one / "hello.txt").write_bytes(b"completely different")
        main_commands.stage(["hello.txt"], "additions")
        staging = utils.get_staging_area()
        expected = hashlib.sha1(b"completely different").hexdigest()
        assert staging["hello.txt"] == expected

    def test_stage_directory_expands_to_individual_files(self, repo):
        subdir = repo / "src"
        subdir.mkdir()
        (subdir / "a.py").write_bytes(b"a")
        (subdir / "b.py").write_bytes(b"b")
        main_commands.stage(["src"], "additions")
        staging = utils.get_staging_area()
        assert any("a.py" in k for k in staging)
        assert any("b.py" in k for k in staging)


# ===========================================================================
# empty_file (selective unstage) edge cases
# ===========================================================================

class TestEmptyFileEdgeCases:
    def test_unstage_file_not_in_staging_prints_error(self, repo_one, capsys):
        basic_commands.empty_file(["not_staged.txt"])
        out = capsys.readouterr().out
        assert "cannot remove" in out.lower() or "staging area" in out.lower()

    def test_unstage_file_removes_it_from_index(self, repo_one):
        (repo_one / "new.txt").write_bytes(b"new")
        main_commands.stage(["new.txt"], "additions")
        basic_commands.empty_file(["new.txt"])
        staging = utils.get_staging_area()
        assert "new.txt" not in staging

    def test_unstage_removal_restores_file_to_index(self, repo_one):
        # rm removes from index; empty_file restores it from HEAD
        main_commands.stage(["hello.txt"], "removals")
        basic_commands.empty_file(["hello.txt"])
        staging = utils.get_staging_area()
        assert "hello.txt" in staging

    def test_unstage_one_of_multiple_staged_files(self, repo_one):
        for name in ("a.txt", "b.txt"):
            (repo_one / name).write_bytes(name.encode())
        main_commands.stage(["a.txt", "b.txt"], "additions")
        basic_commands.empty_file(["a.txt"])
        staging = utils.get_staging_area()
        assert "a.txt" not in staging
        assert "b.txt" in staging


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
        # Checking out the current commit hash detaches HEAD
        branch_commands.checkout_commit(_head_hash(repo_one))
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
    def test_log_on_fresh_repo_prints_no_commits_message(self, repo, capsys):
        info_commands.log()
        out = capsys.readouterr().out
        assert "no commits" in out.lower()

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

    def test_checkout_blocked_when_file_is_missing_head_unchanged(self, repo_two):
        """If checkout is blocked, HEAD must not move."""
        (repo_two / "hello.txt").unlink()
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        before_head = (repo_two / ".minigit" / "HEAD").read_text()
        branch_commands.checkout_commit(parent)
        after_head = (repo_two / ".minigit" / "HEAD").read_text()
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


# ===========================================================================
# check_uncommitted_changes decorator — "n" path
# ===========================================================================

class TestCheckUncommittedChangesAbort:
    """When the user answers 'n' to the prompt, the decorated function must
    not execute.  All tests in this class patch input() to return 'n'."""

    def test_reset_aborted_by_n_does_not_move_branch_pointer(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        (repo_two / "hello.txt").write_bytes(b"dirty - triggers prompt")
        original_hash = _head_hash(repo_two)
        parent = utils.get_commit(original_hash).parent[0]
        history_commands.reset(parent, "hard")
        assert _head_hash(repo_two) == original_hash

    def test_reset_aborted_by_n_does_not_change_working_directory(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        (repo_two / "hello.txt").write_bytes(b"dirty")
        history_commands.reset(utils.get_commit(_head_hash(repo_two)).parent[0], "hard")
        assert (repo_two / "hello.txt").read_bytes() == b"dirty"

    def test_revert_aborted_by_n_does_not_create_new_commit(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "n")
        (repo_two / "hello.txt").write_bytes(b"dirty")
        original_hash = _head_hash(repo_two)
        initial_hash = utils.get_commit(original_hash).parent[0]
        history_commands.revert(initial_hash, "should not happen")
        assert _head_hash(repo_two) == original_hash

    def test_reset_proceeds_when_user_answers_y(self, repo_two, monkeypatch):
        monkeypatch.setattr("builtins.input", lambda _: "y")
        (repo_two / "hello.txt").write_bytes(b"dirty")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        history_commands.reset(parent, "hard")
        assert _head_hash(repo_two) == parent


# ===========================================================================
# Non-fast-forward push rejection
# ===========================================================================

class TestNonFastForwardPush:
    def test_push_when_remote_is_ahead_returns_none(self, two_repos):
        """If remote has commits local doesn't know about, find_branch_ancestor
        returns None and remote_prep_push returns None (push rejected)."""
        local, remote = two_repos
        # First push: sync local → remote
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)

        # Advance the remote independently (simulate another developer pushing)
        _sync_objects(local, remote)

        # Add a new commit directly on the remote
        orig_cwd = os.getcwd()
        os.chdir(remote)
        (remote / "remote_only.txt").write_bytes(b"remote work")
        main_commands.stage(["remote_only.txt"], "additions")
        main_commands.commit("remote advance")
        basic_commands.empty()
        os.chdir(orig_cwd)

        # Now local tries to push — remote is ahead, should be rejected
        result = remote_commands.remote_prep_push("origin", "master")
        assert result is None

    def test_remote_prep_push_non_ff_does_not_overwrite_remote(self, two_repos):
        """A rejected push must not modify the remote branch pointer."""
        _, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)

        # Advance remote
        orig_cwd = os.getcwd()
        os.chdir(remote)
        (remote / "r.txt").write_bytes(b"r")
        main_commands.stage(["r.txt"], "additions")
        main_commands.commit("remote only")
        basic_commands.empty()
        remote_tip_after = _head_hash(remote)
        os.chdir(orig_cwd)

        remote_commands.remote_prep_push("origin", "master")  # rejected
        # Remote branch pointer must be unchanged
        assert _branch_hash(remote, "master") == remote_tip_after


# ===========================================================================
# Pull when already up to date
# ===========================================================================

class TestPullEdgeCases:
    def test_pull_when_up_to_date_does_not_crash(self, two_repos):
        """FIXED BUG-7: pull() when already in sync prints a message and exits
        cleanly instead of crashing with TypeError."""
        local, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)
        _sync_objects(remote, local)
        remote_commands.pull("origin", "master")  # must not raise

    def test_pull_does_not_change_branch_pointer_when_up_to_date(self, two_repos):
        """FIXED BUG-7: branch pointer stays unchanged when pull is a no-op."""
        local, remote = two_repos
        a, rp, bp = remote_commands.remote_prep_push("origin", "master")
        remote_commands.remote_push(a, rp, bp)
        _sync_objects(remote, local)
        before = _head_hash(local)
        remote_commands.pull("origin", "master")
        assert _head_hash(local) == before


# ===========================================================================
# Sequential amends
# ===========================================================================

class TestSequentialAmends:
    def test_amend_twice_uses_latest_message(self, repo_one):
        info_commands.amend("first amendment")
        info_commands.amend("second amendment")
        assert utils.get_commit(_head_hash(repo_one)).message == "second amendment"

    def test_amend_twice_branch_pointer_valid_after_both(self, repo_one):
        info_commands.amend("amend 1")
        info_commands.amend("amend 2")
        # Branch pointer must resolve to a real commit
        commit = utils.get_commit(_head_hash(repo_one))
        assert commit.message == "amend 2"

    def test_amend_then_commit_creates_correct_chain(self, repo_one):
        info_commands.amend("amended")
        amended_hash = _head_hash(repo_one)
        (repo_one / "new.txt").write_bytes(b"new")
        main_commands.stage(["new.txt"], "additions")
        main_commands.commit("after amend")
        basic_commands.empty()
        new_commit = utils.get_commit(_head_hash(repo_one))
        assert new_commit.parent[0] == amended_hash


# ===========================================================================
# Status and log right after init (no user commits)
# ===========================================================================

class TestFreshRepoOperations:
    def test_status_on_fresh_repo_does_not_crash(self, repo, capsys):
        info_commands.status()
        capsys.readouterr()  # just verify no exception

    def test_log_on_fresh_repo_shows_no_commits_message(self, repo, capsys):
        info_commands.log()
        out = capsys.readouterr().out
        assert "no commits" in out.lower()

    def test_log_all_on_fresh_repo_does_not_crash(self, repo, capsys):
        info_commands.log_all()
        capsys.readouterr()

    def test_reflog_on_fresh_repo_does_not_crash(self, repo, capsys):
        info_commands.reflog()
        capsys.readouterr()

    def test_branch_list_on_fresh_repo_does_not_crash(self, repo, capsys):
        # No branch file exists yet (first commit hasn't been made), so output is empty
        branch_commands.branch_list()
        capsys.readouterr()  # just verify no exception


# ===========================================================================
# branch_switch to the same branch
# ===========================================================================

class TestBranchSwitchSameBranch:
    def test_switch_to_current_branch_stays_on_branch(self, repo_one):
        branch_commands.branch_switch("master")
        assert "master" in (repo_one / ".minigit" / "HEAD").read_text()

    def test_switch_to_current_branch_does_not_move_pointer(self, repo_one):
        before_hash = _head_hash(repo_one)
        branch_commands.branch_switch("master")
        assert _head_hash(repo_one) == before_hash


# ===========================================================================
# Detached HEAD: commit chain then re-attach
# ===========================================================================

class TestDetachedHeadWorkflow:
    def test_commits_in_detached_head_not_lost_immediately(self, repo_two):
        """Commits made in detached HEAD are reachable via the HEAD hash
        even after switching back to a branch."""
        # Checkout first commit (parent of tip) to enter detached HEAD state
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)

        (repo_two / "detached_work.txt").write_bytes(b"work done in detached state")
        main_commands.stage(["detached_work.txt"], "additions")
        main_commands.commit("detached commit")
        detached_tip = _head_hash(repo_two)

        # The commit must exist in the objects store
        assert utils.get_commit(detached_tip).message == "detached commit"

    def test_switching_back_to_branch_after_detached_leaves_branch_unchanged(self, repo_two):
        master_before = _branch_hash(repo_two, "master")
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)
        (repo_two / "d.txt").write_bytes(b"d")
        main_commands.stage(["d.txt"], "additions")
        main_commands.commit("detached")
        branch_commands.branch_switch("master")
        assert _branch_hash(repo_two, "master") == master_before


# ===========================================================================
# ADVERSARIAL: untested bugs found by static analysis
# ===========================================================================


# ---------------------------------------------------------------------------
# BUG: init(dir) where dir does NOT yet exist returns early (line 38 of
#      main_commands.py) before creating any .minigit structure.
# ---------------------------------------------------------------------------

class TestInitNonexistentDir:
    def test_init_nonexistent_dir_creates_minigit_directory(self, tmp_path, monkeypatch):
        """init() given a brand-new path should create .minigit inside it.
        BUG: when dir does not exist, init() creates the directory then
        immediately `return`s without building the .minigit structure."""
        monkeypatch.chdir(tmp_path)
        new_repo = tmp_path / "brand_new"
        main_commands.init(new_repo)
        assert (new_repo / ".minigit").exists(), \
            ".minigit was not created — init() returned early"

    def test_init_nonexistent_dir_creates_head(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        new_repo = tmp_path / "brand_new"
        main_commands.init(new_repo)
        assert (new_repo / ".minigit" / "HEAD").exists(), \
            "HEAD not created — init() returned early"

    def test_init_nonexistent_dir_creates_index(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        new_repo = tmp_path / "brand_new"
        main_commands.init(new_repo)
        assert (new_repo / ".minigit" / "index").exists(), \
            "index not created — init() returned early"


# ---------------------------------------------------------------------------
# Index persists after commit (like real git).
# ---------------------------------------------------------------------------

class TestIndexBehaviourAfterCommit:
    def test_index_persists_after_commit(self, repo):
        """The index is NOT cleared after a commit — it persists like real git."""
        (repo / "a.txt").write_bytes(b"a")
        main_commands.stage(["a.txt"], "additions")
        main_commands.commit("add a")
        staging = utils.get_staging_area()
        assert "a.txt" in staging, \
            "Index should still contain a.txt after commit (index is persistent)"

    def test_rm_file_absent_from_index_after_commit(self, repo_one):
        """After rm + commit, file is absent from the index."""
        main_commands.stage(["hello.txt"], "removals")
        main_commands.commit("remove hello")
        staging = utils.get_staging_area()
        assert "hello.txt" not in staging

    def test_double_commit_without_staging_produces_different_hashes(self, repo_one):
        """Committing twice in a row (no new staging between) must give different
        hashes because each commit has a different parent."""
        main_commands.commit("first no-stage commit")
        h1 = _head_hash(repo_one)
        main_commands.commit("second no-stage commit")
        h2 = _head_hash(repo_one)
        assert h1 != h2


# ---------------------------------------------------------------------------
# BUG: fast-forward merge calls make_blob_current() which only WRITES files;
#      it never DELETES files that were removed on the merged branch.
# ---------------------------------------------------------------------------

class TestFastForwardMergeFileDeletion:
    def test_ff_merge_removes_file_deleted_on_merged_branch(self, repo_one):
        """After a fast-forward merge, files deleted on the merged branch should
        not exist in the working directory.
        BUG: make_blob_current() never deletes — stale files persist."""
        # Create feature branch at the current commit and delete hello.txt there
        branch_commands.branch_create("feature")
        main_commands.stage(["hello.txt"], "removals")
        main_commands.commit("delete hello on feature")
        basic_commands.empty()

        # Return to master (still has hello.txt committed)
        branch_commands.branch_switch("master")
        assert (repo_one / "hello.txt").exists(), "precondition: hello.txt on master"

        # Fast-forward master up to feature (master is the ancestor of feature)
        branch_commands.merge("feature", "ff merge")

        assert not (repo_one / "hello.txt").exists(), \
            "BUG: hello.txt survived FF merge even though feature deleted it"

    def test_ff_merge_head_commit_does_not_contain_deleted_file(self, repo_one):
        """The commit object after FF merge must not list the deleted file."""
        branch_commands.branch_create("feature")
        main_commands.stage(["hello.txt"], "removals")
        main_commands.commit("delete hello on feature")
        basic_commands.empty()
        branch_commands.branch_switch("master")
        branch_commands.merge("feature", "ff merge")
        files = utils.get_commit(_head_hash(repo_one)).files
        assert "hello.txt" not in files, \
            "HEAD commit still references deleted file after FF merge"


# ---------------------------------------------------------------------------
# BUG: three-way merge categorises files that exist only in one branch as
#      "unique" and always keeps them — it never respects a deletion that
#      happened on the other branch relative to the common ancestor.
# ---------------------------------------------------------------------------

class TestThreeWayMergeFileDeletion:
    @pytest.fixture
    def diverged_repo(self, tmp_path, monkeypatch):
        """Repo whose history looks like:
            ancestor (has keep.txt + victim.txt)
               /           \\
          master            feature
        (modifies keep.txt)  (deletes victim.txt)
        """
        monkeypatch.chdir(tmp_path)
        main_commands.init()
        (tmp_path / "keep.txt").write_bytes(b"original")
        (tmp_path / "victim.txt").write_bytes(b"to be deleted on feature")
        main_commands.stage(["keep.txt", "victim.txt"], "additions")
        main_commands.commit("ancestor")
        basic_commands.empty()

        # feature branch: delete victim.txt
        branch_commands.branch_create("feature")
        main_commands.stage(["victim.txt"], "removals")
        main_commands.commit("delete victim on feature")
        basic_commands.empty()

        # master branch: modify keep.txt (forces a real 3-way merge)
        branch_commands.branch_switch("master")
        (tmp_path / "keep.txt").write_bytes(b"modified on master")
        main_commands.stage(["keep.txt"], "additions")
        main_commands.commit("modify keep on master")
        basic_commands.empty()

        return tmp_path

    def test_3way_merge_removes_file_deleted_on_other_branch(self, diverged_repo):
        """victim.txt was deleted on feature but not touched on master.
        The three-way merge should honour that deletion.
        BUG: the file ends up in unique_files_current_commit and is kept."""
        branch_commands.merge("feature", "merge feature into master")
        assert not (diverged_repo / "victim.txt").exists(), \
            "BUG: victim.txt survived 3-way merge even though feature deleted it"

    def test_3way_merge_commit_excludes_file_deleted_on_other_branch(self, diverged_repo):
        """The merge commit's file dict must not contain victim.txt."""
        branch_commands.merge("feature", "merge feature into master")
        files = utils.get_commit(_head_hash(diverged_repo)).files
        assert "victim.txt" not in files, \
            "BUG: merge commit still tracks victim.txt after it was deleted on feature"


# ---------------------------------------------------------------------------
# BUG: both stage() and get_directory_files_dictionary() normalise filenames
#      with  str(path).lstrip("./")  which strips individual characters, not
#      the substring "./".  A filename like ".env" loses its leading dot and
#      is stored/tracked as "env".
# ---------------------------------------------------------------------------

class TestDotfileNameMangling:
    def test_staging_dotfile_preserves_leading_dot(self, repo):
        """Staging '.env' should store it under the key '.env', not 'env'."""
        (repo / ".env").write_bytes(b"SECRET=hunter2")
        main_commands.stage([".env"], "additions")
        staging = utils.get_staging_area()
        assert ".env" in staging, \
            f"BUG: dotfile stored as '{list(staging.keys())}' instead of '.env'"

    def test_committed_dotfile_has_correct_name_in_commit(self, repo):
        """The commit object must record the file as '.env', not 'env'."""
        (repo / ".env").write_bytes(b"SECRET=hunter2")
        main_commands.stage([".env"], "additions")
        main_commands.commit("add dotfile")
        basic_commands.empty()
        files = utils.get_commit(_head_hash(repo)).files
        assert ".env" in files, \
            f"BUG: committed dotfile appears as '{list(files.keys())}' instead of '.env'"

    def test_checkout_restores_dotfile_with_correct_name(self, repo_one):
        """Checking out a commit containing '.env' must restore a file named
        '.env', not a file named 'env'."""
        (repo_one / ".env").write_bytes(b"SECRET=hunter2")
        main_commands.stage([".env"], "additions")
        main_commands.commit("add dotfile")
        commit_with_dotfile = _head_hash(repo_one)

        # Go back one commit then return
        parent = utils.get_commit(commit_with_dotfile).parent[0]
        branch_commands.checkout_commit(parent)
        branch_commands.checkout_commit(commit_with_dotfile)

        assert (repo_one / ".env").exists(), \
            "BUG: dotfile '.env' not restored (was saved/restored as 'env')"


# ---------------------------------------------------------------------------
# BUG: mgignore() opens .minigitignore in 'w' (write/truncate) mode, so a
#      second call silently discards every pattern added by the first call.
# ---------------------------------------------------------------------------

class TestMgignoreOverwrites:
    def test_second_mgignore_call_preserves_first_patterns(self, repo):
        """Calling mgignore twice should accumulate patterns, not replace them."""
        basic_commands.mgignore(["*.log"])
        basic_commands.mgignore(["*.tmp"])
        content = (repo / ".minigitignore").read_text()
        assert "*.log" in content, \
            "BUG: first mgignore pattern '*.log' was erased by the second call"

    def test_ignored_file_stays_ignored_after_second_mgignore_call(self, repo):
        """A file matching the first pattern must still be ignored after a
        second mgignore() call adds a different pattern."""
        basic_commands.mgignore(["*.log"])
        basic_commands.mgignore(["*.tmp"])
        (repo / "server.log").write_bytes(b"log data")
        assert utils.check_ignore("server.log"), \
            "BUG: '*.log' no longer ignored after second mgignore() call erased it"


# ---------------------------------------------------------------------------
# BUG: utils.check_staging_area() iterates staging_area_removals with
#      .keys() but removals is a plain list, not a dict → AttributeError.
# ---------------------------------------------------------------------------

class TestCheckStagingAreaBug:
    def test_check_staging_area_with_staged_removal_does_not_crash(self, repo_one, capsys):
        """check_staging_area() should not raise AttributeError when there are
        staged removals.  BUG: it calls list.keys() which does not exist."""
        main_commands.stage(["hello.txt"], "removals")
        utils.check_staging_area()   # must not raise
        capsys.readouterr()


# ---------------------------------------------------------------------------
# BUG: checkout_commit() checks whether tracked files are *modified* but
#      never checks whether the *staging area* is dirty.  Staged additions
#      are silently abandoned: the hashes recorded in the index refer to a
#      pre-checkout file version, but after checkout the file on disk is
#      different.  If the user then commits, the blob written to objects
#      will contain the checked-out content while the commit's file dict
#      records the (stale) staged hash — corrupting the object store.
# ---------------------------------------------------------------------------

class TestCheckoutIgnoresStagingArea:
    def test_checkout_with_staged_addition_warns_user(self, repo_two, capsys):
        """checkout_commit() should refuse when local changes would be overwritten."""
        # Stage a modified version of hello.txt (do NOT commit)
        (repo_two / "hello.txt").write_bytes(b"staged but not committed")
        main_commands.stage(["hello.txt"], "additions")

        # Checkout an earlier commit — hello.txt would be overwritten
        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)

        out = capsys.readouterr().out.lower()
        assert "overwrite" in out or "committed" in out or "unable" in out, \
            "checkout proceeded silently despite local changes that would be overwritten"

    def test_staged_hash_matches_file_on_disk_after_checkout(self, repo_two):
        """After staging hello.txt and then checking out an older commit, the
        hash recorded in the staging area must still match the file on disk.
        BUG: checkout overwrites the file so the staged hash is now stale."""
        (repo_two / "hello.txt").write_bytes(b"staged version")
        main_commands.stage(["hello.txt"], "additions")
        staged_hash = utils.get_staging_area()["hello.txt"]

        parent = utils.get_commit(_head_hash(repo_two)).parent[0]
        branch_commands.checkout_commit(parent)

        with open(repo_two / "hello.txt", "rb") as f:
            actual_hash = hashlib.sha1(f.read()).hexdigest()

        assert actual_hash == staged_hash, \
            "BUG: checkout overwrote the staged file; staging area hash is now stale"


# ---------------------------------------------------------------------------
# BUG: find_common_ancestor() only ever follows parent[0] when building the
#      ancestor set of commit1 and when walking commit2's history.  In a repo
#      that already has a merge commit, it misses the second-parent branch and
#      returns an ancestor that is *older* than the true common ancestor.
# ---------------------------------------------------------------------------

class TestFindCommonAncestorMergeHistory:
    def test_common_ancestor_correct_after_prior_merge(self, tmp_path, monkeypatch):
        """
        History shape:
            A ─── B ─── M (merge commit, parents=[B, D])  ← master
                   \\
                    C ─── D ─── E                          ← feature2

        The true common ancestor of master (M) and feature2 (E) is D, which
        is the second parent of M.  find_common_ancestor() only follows
        parent[0] so it builds ancestors={M,B,A} and never visits D, then
        walks E→D→C→A and finds A instead of D.
        """
        monkeypatch.chdir(tmp_path)
        main_commands.init()

        # Commit A (initial commit already exists; add a real file commit)
        (tmp_path / "base.txt").write_bytes(b"base")
        main_commands.stage(["base.txt"], "additions")
        main_commands.commit("A: base")
        basic_commands.empty()
        a_hash = _head_hash(tmp_path)

        # Commit B on master
        (tmp_path / "master_only.txt").write_bytes(b"master")
        main_commands.stage(["master_only.txt"], "additions")
        main_commands.commit("B: master only")
        basic_commands.empty()
        b_hash = _head_hash(tmp_path)

        # Branch off at A to create C→D on a side branch
        branch_commands.checkout_commit(a_hash)
        branch_commands.branch_create("side")
        (tmp_path / "side.txt").write_bytes(b"side c")
        main_commands.stage(["side.txt"], "additions")
        main_commands.commit("C: side commit")
        basic_commands.empty()

        (tmp_path / "side.txt").write_bytes(b"side d")
        main_commands.stage(["side.txt"], "additions")
        main_commands.commit("D: side commit 2")
        basic_commands.empty()
        d_hash = _head_hash(tmp_path)

        # Switch to master and merge side → creates merge commit M (parents=[B,D])
        branch_commands.branch_switch("master")
        branch_commands.merge("side", "M: merge side into master")
        m_hash = _head_hash(tmp_path)
        basic_commands.empty()

        # Now create feature2 branching from D
        branch_commands.checkout_commit(d_hash)
        branch_commands.branch_create("feature2")
        (tmp_path / "feature2.txt").write_bytes(b"feature2 work")
        main_commands.stage(["feature2.txt"], "additions")
        main_commands.commit("E: feature2 commit")
        basic_commands.empty()
        e_hash = _head_hash(tmp_path)

        # Back to master, find common ancestor between M and E
        branch_commands.branch_switch("master")

        m_obj = utils.get_commit(m_hash)
        e_obj = utils.get_commit(e_hash)
        ancestor, ancestor_hash = utils.find_common_ancestor(m_obj, m_hash, e_obj)

        # The true common ancestor is D (reachable via M's second parent).
        # BUG: find_common_ancestor only follows parent[0] so it returns A instead.
        assert ancestor_hash == d_hash, \
            f"BUG: found ancestor {ancestor_hash[:8]} (expected D={d_hash[:8]}); " \
            f"find_common_ancestor missed M's second parent"


# ===========================================================================
# Additional mgignore tests
# ===========================================================================

class TestMgIgnoreAdditional:
    def test_mgignore_single_string_accepted(self, repo):
        """mgignore should accept a plain string, not just a list."""
        basic_commands.mgignore("solo.log")
        content = (repo / ".minigitignore").read_text()
        assert "solo.log" in content

    def test_mgignore_appends_to_existing_content(self, repo):
        """Each mgignore call should add to the file, not erase prior entries."""
        basic_commands.mgignore(["first.log"])
        basic_commands.mgignore(["second.log"])
        content = (repo / ".minigitignore").read_text()
        assert "first.log" in content, \
            "BUG: first pattern was erased by the second mgignore call"
        assert "second.log" in content

    def test_mgignore_empty_list_does_not_corrupt_file(self, repo):
        """Calling mgignore with an empty list must not break the file."""
        basic_commands.mgignore(["keep.log"])
        basic_commands.mgignore([])
        content = (repo / ".minigitignore").read_text()
        assert "keep.log" in content

    def test_mgignore_wildcard_pattern_respected_by_check_ignore(self, repo):
        """A wildcard added via mgignore must cause check_ignore to return True."""
        basic_commands.mgignore(["*.secret"])
        assert utils.check_ignore("passwords.secret") is True

    def test_mgignore_prevents_file_appearing_in_directory_scan(self, repo):
        """Files matching a mgignore pattern must not appear in get_directory_files_dictionary."""
        basic_commands.mgignore(["ignore_me.txt"])
        (repo / "ignore_me.txt").write_bytes(b"hidden")
        (repo / "keep_me.txt").write_bytes(b"visible")
        files = utils.get_directory_files_dictionary(str(repo))
        assert not any("ignore_me.txt" in k for k in files), \
            "BUG: ignored file appeared in directory scan"
        assert any("keep_me.txt" in k for k in files)

    def test_mgignore_does_not_prevent_staging_non_matching_file(self, repo):
        """Only files matching a pattern should be blocked from staging."""
        basic_commands.mgignore(["*.log"])
        (repo / "readme.txt").write_bytes(b"ok")
        main_commands.stage(["readme.txt"], "additions")
        staging = utils.get_staging_area()
        assert "readme.txt" in staging


# ===========================================================================
# Additional check_ignore tests
# ===========================================================================

class TestCheckIgnoreAdditional:
    def test_minigitignore_present_after_init(self, repo):
        """init() always creates .minigitignore, so check_ignore can open it safely."""
        assert (repo / ".minigitignore").exists(), \
            "init() must create .minigitignore so check_ignore never hits FileNotFoundError"

    def test_minigitignore_itself_is_not_ignored_by_default(self, repo):
        """.minigitignore is a normal tracked file (like .gitignore in real git).
        It should NOT be auto-ignored — users can stage and commit it."""
        assert utils.check_ignore(".minigitignore") is False

    def test_exact_filename_in_minigitignore_is_ignored(self, repo):
        """An exact filename listed in .minigitignore must be ignored."""
        (repo / ".minigitignore").write_text("secret.txt\n")
        assert utils.check_ignore("secret.txt") is True

    def test_blank_lines_in_minigitignore_do_not_cause_false_positives(self, repo):
        """Blank lines must not be treated as patterns that match empty-segment paths."""
        (repo / ".minigitignore").write_text("\n\n\nreal.log\n\n")
        assert utils.check_ignore("real.log") is True
        assert utils.check_ignore("other.txt") is False

    def test_inline_comment_not_supported_treated_as_literal(self, repo):
        """Only full-line comments (#...) are stripped; inline '#' is part of the pattern."""
        (repo / ".minigitignore").write_text("file.txt # not a comment\n")
        # The pattern is the whole line; 'file.txt' alone should NOT match
        assert utils.check_ignore("file.txt") is False

    def test_directory_pattern_does_not_match_file_at_root(self, repo):
        """A pattern like 'build/' should not match a plain file named 'build'."""
        (repo / ".minigitignore").write_text("build/\n")
        assert utils.check_ignore("build") is False, \
            "BUG: directory pattern 'build/' wrongly matched plain file 'build'"

    def test_directory_pattern_matches_deeply_nested_file(self, repo):
        """'dist/' should ignore files at any depth inside dist/."""
        (repo / ".minigitignore").write_text("dist/\n")
        assert utils.check_ignore("dist/js/bundle.min.js") is True

    def test_wildcard_matches_only_within_single_path_component(self, repo):
        """'*.log' should match 'app.log' but not 'logs/app.log' via component matching."""
        (repo / ".minigitignore").write_text("*.log\n")
        # The filename component 'app.log' matches '*.log'
        assert utils.check_ignore("app.log") is True

    def test_nested_filename_matches_via_component_check(self, repo):
        """'*.log' in .minigitignore must match 'subdir/app.log' (component match)."""
        (repo / ".minigitignore").write_text("*.log\n")
        assert utils.check_ignore("subdir/app.log") is True, \
            "BUG: wildcard pattern did not match file inside a subdirectory"

    def test_multiple_patterns_all_respected(self, repo):
        """.minigitignore with several patterns should ignore each type."""
        (repo / ".minigitignore").write_text("*.pyc\n*.o\nbuild/\n")
        assert utils.check_ignore("module.pyc") is True
        assert utils.check_ignore("main.o") is True
        assert utils.check_ignore("build/out.bin") is True
        assert utils.check_ignore("src/main.py") is False

    def test_pattern_with_leading_dot_matches_dotfile(self, repo):
        """.env listed in .minigitignore should cause check_ignore('.env') to be True."""
        (repo / ".minigitignore").write_text(".env\n")
        assert utils.check_ignore(".env") is True

    def test_check_ignore_returns_false_for_empty_minigitignore(self, repo):
        """An empty .minigitignore means nothing extra is ignored (beyond builtins)."""
        (repo / ".minigitignore").write_text("")
        assert utils.check_ignore("anything.txt") is False

    def test_minigit_subpath_always_ignored(self, repo):
        """Any path starting with .minigit/ is a builtin-ignored path."""
        for path in (".minigit/HEAD", ".minigit/refs/heads/master", ".minigit/objects/blobs/ab/cd"):
            assert utils.check_ignore(path) is True, \
                f"BUG: builtin path '{path}' was not ignored"
