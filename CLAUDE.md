# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Toolchain Labs built commercial solutions around the Pants OSS build system, including remote execution, caching, and build optimization. This repo is a snapshot of Toolchain's proprietary codebase (May 2023), now Apache 2.0 licensed. It is a polyglot codebase (Python, Rust, Go, TypeScript, Shell).

## Build System

This repo uses [Pants](https://www.pantsbuild.org/) v2.16.0 as its build tool. The `./pants` wrapper script invokes Pants.

### Common Commands

```shell
# Run all Python tests
./pants test src/python::

# Run tests for a specific directory
./pants test src/python/toolchain/buildsense/::

# Run a single test file
./pants test src/python/toolchain/util/some_test.py

# Lint (all Python linters: black, isort, flake8, pylint, mypy, bandit, autoflake, pyupgrade, docformatter, ruff)
./pants lint src/python::

# Format code (black + isort for Python, shfmt for shell)
./pants fmt src/python::

# Type check
./pants check src/python::

# List targets
./pants list src/python/toolchain/service::
```

### Rust (not managed by Pants)

Rust code lives in `src/rust/` as a Cargo workspace. CI uses standard cargo commands:
```shell
cd src/rust
cargo fmt --all -- --check
cargo build
cargo test
cargo clippy --all-targets -- -D warnings
```
Rust toolchain version: 1.68.0 (see `rust-toolchain.toml`).

### Node.js (not managed by Pants)

Frontend apps are in `src/node/`. Uses Yarn for package management, Jest for tests, Cypress for E2E.

## Code Style

- **Python**: Black formatter, line length 120, target Python 3.9 (`CPython>=3.9,<3.10`)
- **isort**: multi_line_output=3, trailing commas, known_first_party=`toolchain`
- **Shell**: shfmt with `-i 2 -ci -sr` (2-space indent, case indent, redirect spacing)
- Lint configs live in `build-support/python/` (flake8, pylintrc, mypy.ini, bandit.yaml)
- Python project-level config in `pyproject.toml` (Black, isort, ruff settings)
- Copyright headers enforced via `build-support/preambles/config.yaml`

## Architecture

### Python Services (`src/python/toolchain/service/`)

Django-based microservices. Each service is a Django "project" composed of reusable Django "apps" that live elsewhere under `src/python/toolchain/`. Service project-level files (settings.py, urls.py, gunicorn_conf.py) live in the service directory; reusable app code lives in its own package.

Run a local dev service:
```shell
./src/python/toolchain/service/<service_name>/manage.py runserver
```

Key services: `buildsense/api` (build analytics), `users`, `webhooks`, `servicerouter`, `infosite`, `toolshed`, `payments`, `notifications`.

Service definitions are in `src/python/toolchain/config/services.json`.

### Remote Execution Platform (`src/rust/`)

REAPI-compliant remote execution system. Request flow: **Client → AWS ALB → proxy-server → execution-server → Buildbox worker**.

Rust workspace crates:
- **proxy** / **proxy_server**: Authenticates gRPC requests (JWT), dispatches to backends. Uses `ginepro` for in-process load balancing across backend pods.
- **execution** / **execution_server**: Queues execution requests; workers pull work via Bots protocol (leases).
- **storage** / **storage_server**: Content Addressable Storage (CAS) and Action Cache.
- **worker**: Worker process management.
- **protos**: Protocol buffer definitions (REAPI, Bots protocol, CAS).
- **digest**, **grpc_util**, **execution_util**: Shared utilities.

Detailed architecture: `docs/remoting/life-of-a-request.md`.

### Deployment (`prod/`)

- **Docker images**: `prod/docker/` — Dockerfiles for Django services (gunicorn+nginx) and Rust services.
- **Helm charts**: `prod/helm/` — Kubernetes deployment. Per-service charts under `prod/helm/services/`.
- **Terraform**: `prod/terraform/` — AWS infrastructure (ECR, IAM, DynamoDB, S3, ALB).
- **Kubernetes**: AWS EKS clusters (dev, prod, remoting). Namespace isolation per developer in dev.

### Key Source Directories

- `src/python/toolchain/pants/` — Custom Pants build system plugins
- `src/python/toolchain/django/` — Shared Django utilities and common code
- `src/python/toolchain/base/` — Core utilities and templates
- `src/python/toolchain/remoting/` — Python-side remoting infrastructure
- `3rdparty/` — Dependency lockfiles (two Python resolves: `default-toolchain` and `pants-plugin`)

## Pants Dependency Management

Two Python resolves exist:
- `default-toolchain`: Main application code (`3rdparty/python/default_toolchain.lock`)
- `pants-plugin`: Pants plugin code (`3rdparty/python/pants_plugin.lock`)

Unowned dependency behavior is set to `error` — all imports must be traceable to BUILD targets.

## Testing

- Tests live alongside source code (pattern: `*_test.py`, `test_*.py`)
- Default test timeout: 60 seconds
- pytest v7.3.1 with pytest-icdiff for diff output
- CI config: `pants.ci.toml` (enables coverage, verbose mode, 4 parallel processes)
