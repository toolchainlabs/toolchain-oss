# Toolchain

[![CircleCI](https://circleci.com/gh/toolchainlabs/toolchain/tree/master.svg?style=svg&circle-token=9cfd5257265ef84a3b6de0db319ed4adeee9c903)](https://circleci.com/gh/toolchainlabs/toolchain/tree/master)

[![codecov](https://codecov.io/gh/toolchainlabs/toolchain/branch/master/graph/badge.svg?token=DlqpSfuPM6)](https://codecov.io/gh/toolchainlabs/toolchain)

## Getting Started

See [SETUP.md](./SETUP.md).

## Pants

This repo uses the [Pants](https://www.pantsbuild.org/) build tool.
Familiarize yourself with it at the above link, if necessary.

## Top-level directories

- [`3rdparty/`](./3rdparty/): Build targets referencing external code in various languages.
- [`build-support/`](./build-support/): Support files for various Pants tasks.
- [`dist/`](./dist/): Pants puts distributable artifacts here.  Created on-demand.
- [`dist.docker/`](./dist.docker/): Same as `dist`, but for artifacts built when running Pants in a docker container.
- [`prod/`](./prod/): Code and config used to deploy, update and manage production services.
- [`src/`](./src/): Source and unit test code in various languages.
- [`test/`](./test/): Tests that don't belong next to specific source code, e.g., end-to-end integration tests.
- [`testdata/`](./testdata/): Inputs for tests that act on source code.

See the README.md files in subdirectories for more information.

## Important Pointers

- [Our various services](./src/python/toolchain/service/README.md) and
  how to run local dev instances of them.
- [How we package and deploy services](./prod/helm/README.md) to Kubernetes,
  both for production and dev use.
- How to connect to the [bastion](./prod/python/toolchain_prod/scripts/BASTION.md) and the [dev box](./docs/devbox.md).
- Our [code review guide](https://docs.google.com/document/d/1IknQ45LuTq36elGNGwr8E7gj2hHX4V_8yoJ6APIsUOo).
