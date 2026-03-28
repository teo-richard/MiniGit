Project inspired by UCB's CS61B Gitlet. The reason I started this project is because Git and GitHub genuinely confuse me so I figured building a mini version of Git would help me understand what is going on under the hood.

This project is meant to be a slightly more complex version of the CS61B project (and is written in Python instead of Java). The project does not use an online tutorial or online notes. It was architected with my brother over my winter break—we sat down with my iPad and went through what I wanted my MiniGit to do. It's evolved a lot since we scratched out that plan but the main ideas come from that.


## Current State

The project has come a long way from the original ugly if-statement monolith in `minigit.py`. The code is now organized into a `commands/` package with modules grouped by responsibility:

- `main_commands.py` — core operations: `init`, `add`/`remove` (staging)
- `basic_commands.py` — staging area utilities: `empty`, `minigitignore`
- `info_commands.py` — inspection: `status`, `log`, `reflog`, `amend`
- `branch_commands.py` — branching: `switch`, `branch`, `checkout`, `merge`
- `history_commands.py` — history manipulation: `revert`, `reset`
- `remote_commands.py` — remote operations: `remote`, `push`, `fetch`, `pull`

The entry point (`minigit.py`) uses a dispatch table to route commands—no more long if-else chains.

## Supported Commands

| Command | Description |
|---|---|
| `init` | Initialize a new repository |
| `add <files>` | Stage files for commit |
| `remove <files>` | Mark files for removal |
| `empty [-f <file>]` | Clear staging area (or unstage a specific file) |
| `commit <message> [-a]` | Commit staged changes; `-a` to amend last commit message |
| `status` | Show current repository status |
| `log [--all]` | Show commit history; `--all` shows all branches |
| `reflog` | Show every commit ever made in the repo |
| `checkout <hash>` | Check out a specific commit (detached HEAD) |
| `switch <branch> [-c]` | Switch branches; `-c` to create and switch |
| `branch [-d <branch>]` | List branches; `-d` to delete one |
| `merge <branch> [-m]` | Merge a branch into the current branch |
| `revert <hash> [-m]` | Create a new commit that undoes a given commit |
| `reset <hash> [--hard\|--soft]` | Move HEAD to a commit, optionally wiping history |
| `minigitignore <files>` | Add files to `.minigitignore` |
| `remote <name> <path>` | Register a remote repository |
| `push <remote> <branch>` | Push commits to a remote branch |
| `fetch <remote> <branch>` | Fetch commits from a remote branch |
| `pull <remote> <branch>` | Fetch and merge from a remote branch |

## Testing

There are three test files in `tests/`:
- `test_minigit.py` — core command tests
- `test_advanced.py` — branching, merging, and remote tests
- `test_edge_cases.py` — edge cases and error handling

## Transparency Note

1. All the docstrings and many comments in the code are written by Claude Code. However, since this is a learning project, all the actual code is mine. I do read nearly every comment that gets generated.
2. All tests were written by Claude Code.