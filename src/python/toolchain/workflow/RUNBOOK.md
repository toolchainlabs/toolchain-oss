# Workflow system run book

## General overview

For general information and design of the workflow system, see [README](./README.md)

We have several services that run background workflow using this system.

The way to diagnose issues is via logs, sentry, and the Workflow Management UI which is part of [toolshed](./../toolshed/README.md).

## Workflow Management UI

There is a different "instance" of the Workflow Management UI for each service that integrates with it.
For example, the [BuildSense](./../buildsense/README.md) Management UI is [here](https://toolshed.toolchainlabs.com/db/buildsense/workflow/summary/), while the PyPi Crawler Management UI is [here](https://toolshed.toolchainlabs.com/db/pypi/workflow/summary/)
There is a list of links to all Workflow Management UIs for the various services on the [Toolshed home page](https://toolshed.toolchainlabs.com/)

First, in the Workflow Summary Page, the Workflow Status tables has a column counting work units in infeasible state: a non-zero value in this column indicates an issue.
Work units in this state are indication for something gone wrong while they were executing.

To see more information, go to the `Work Exceptions` page and click thru to a a specific exception page to see which part of the code broke and possibly why.

Depending on the error, a retry can be triggered from the exception page by clicking the "mark as feasible" link after doing that click thru to the work unit page to see if it is in succeeded if it failed again.

If there is an actual bug, the same technique should be used to retry the failed work unit after a bug fix has been deployed.
