# Pants related scripts

## scie-pants bootstrap script

This script is used the bootstrap scie-pants.
We want to avoid curling to bash, since this is extermaly dangerous to do over time. both in CI and on developer's machines.
So this script is copied from <https://static.pantsbuild.org/setup/pantsup.sh> as described in the [pants docs](https://www.pantsbuild.org/v2.15/docs/installation)

We have a [GitHub Actions Workflow](../../../.github/workflows/check-upstream-scripts.yml) that will compare this script to the upstream script and will notify slack when they are ouf of sync.
