Project inspired by UCB's CS61B Gitlet. The reason I started this project is because Git and GitHub genuinely confuse me so I figured building a mini version of Git would help me understand what is going on under the hood.

This project is meant to be a slightly more complex version of the CS61B project (and is written in Python instead of Java). The project does not use an online tutorial or online notes. It was architected with my brother over my winter break—we sat down with my iPad and went through what I wanted my MiniGit to do. It's evolved a little since we scratched out that plan but the main ideas come from that.

This `README.md` file hopefully will be updated periodically as I progress throughout the project.  

So far, I have implemented various functions including: init, staging, commit, status, log, commit checkout, merge, branching functions, and revert. I have not yet tested in-depth for edge cases. I have also improved my filters for ignoring files in `.minigitignore` and fixed up the `stage()` function to work with this. Next, I'd like to implement the `reset()` function and add a global commit log.

Also in the spirit of transparency, note that all the docstrings and most of the comments in my code are created by Claude Code. However, since this is a learning project, all the code itself is mine, believe it or not! I hope you can forgive me for taking a shortcut with the commenting though...