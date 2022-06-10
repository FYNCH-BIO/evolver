# How to contribute

Thank you for your interest in contributing to eVOLVER! This document provides a brief set of guidelines for contributing.

# Check out the forum!

New to eVOLVER, or have any questions about how something works or how to do something? Head over to our Discourse forum! We have many guides and resources available and are happy to start a conversation about your eVOLVER and science! https://evolver.bio

# Making a code contribution

We use a "fork and pull" model for collaborative software development.

From the [GitHub Help Page of Using Pull Requests](https://help.github.com/articles/using-pull-requests/): 

"The fork & pull model lets anyone fork an existing repository and push changes to their personal fork without requiring access be granted to the source repository. The changes must then be pulled into the source repository by the project maintainer. This model reduces the amount of friction for new contributors and is popular with open source projects because it allows people to work independently without upfront coordination."

## Getting Started

 * Make sure you have a [GitHub account](https://github.com/signup/free).
 * Create an issue in our issues tracker, assuming one does not already exist.
 * Fork the proper eVOLVER project on GitHub.  For general instructions on forking a GitHub project, see [Forking a Repo](https://help.github.com/articles/fork-a-repo/) and [Syncing a fork](https://help.github.com/articles/syncing-a-fork/).

## Contributing Code Changes via a Pull Request

Once you have forked the repo, you need to create your code contributions within a new branch of your forked repo.  For general background on creating and managing branches within GitHub, see:  [Git Branching and Merging](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging).

* To begin, create a topic branch from where you want to base your work.
* For most cases, this will be the **master branch**.

You usually create a branch like so:

```
git checkout master
git checkout -b [name_of_your_new_branch]
```

You then usually commit code changes, and push your branch back to GitHub like so:

```git push origin [name_of_your_new_branch]```

When you are ready to submit your pull-request:

* Push your branch to your GitHub project.
* Open the pull request to the branch you've based your work on

For more details on submitting a pull-request, please see:  [GitHub Guide to Collaborating with issues and pull requests](https://help.github.com/en/github/collaborating-with-issues-and-pull-requests).

## Branches within eVOLVER
Each eVOLVER repository maintains three branches:

* **master**: This reflects the current release of eVOLVER software. Typically you should not make PRs into this branch.
* **rc**: Release candidate branch. This branch is for new feature development and testing before releasing into master. Once we are ready to release all the new features out we will merge this branch into master.
* **hotfix**: This branch is used for bug fixes that need to immediately go into master and be released before other features in RC are ready. Once bugs are fixed in this branch, the changes are merged into master and rc.

### Getting your changes reviewed

Once you've submitted your pull request, you want
other members of the development community to review
whether integrating your change will cause problems
for any users or the maintainability of the software.

If you have an idea who might be able to spot such issues
in the parts of the code and functionality affected by your changes,
notify them by requesting a review using the **Reviewers** menu
to the right of the summary you just wrote
and/or `@`-mentioning them in a comment. Or reaching out them on [the forum](https://evolver.bio).

Reviewers may request you to rephrase or adjust things
before they allow the changes to be integrated.
If they do, commit the amendments as new, separate changes,
to allow the reviewers to see what changed since they last read your code.
Do not overwrite previously-reviewed commits with
ones that include additional changes (by `--amend`ing or squashing)
until the reviewers approve.
Reviewers may request you to squash such amendment commits afterwards,
or offer to push rewritten versions of your commits themselves.

## Pull Request Reviewers Guide
If someone requests your review on a pull request,
read the title and description and assign any other collaborators
who would want to know about the proposed change.

Decide whether you think that your input is needed,
and that the PR should wait for your further review before being merged.
If not, un-assign yourself as a reviewer and leave a comment.

