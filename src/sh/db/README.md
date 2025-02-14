# Setting up development databases

Our Django apps use various postgresql databases (e.g., a users database, a buildsenses database etc.)

In production each of these might be entirely separate database clusters. However when developing
we typically run a single postgresql instance, with multiple logical databases. This instance can
run either on your local machine, or in a personal dev namespace on a Kubernetes cluster.

## Using a remote dev database

In dev mode our Django services use the local dev db by default.
To point a local Django service at your remote dev db running on Kubernetes, set `USE_REMOTE_DEV_DBS`.

E.g.,

```bash
USE_REMOTE_DEV_DBS=1 ./src/python/toolchain/service/users/ui/manage.py runserver

USE_REMOTE_DEV_DBS=1 ./src/sh/db/migrate.sh  # If you have new migrations to apply.
```

## Setting up a local dev database

First install PostgreSQL on your local machine (e.g., on a Mac, `brew install postgresql`).

Then run

```bash
./src/sh/db/local_db_setup.sh
```

This script will initialize a database data directory at a well-known location (`~/toolchain.local.pgsql`),
and set up logical databases (users, buildsenses, etc.) on that instance. It'll also run all current migrations
against all dbs, and create a superuser.

It will then launch a database process, which will stay running in the background.

This script is idempotent, so if it fails in the middle for any reason, try running it again.

The local dev database instance listens on a non-standard port, so there's generally no harm in leaving it running.
However if you do want to stop it, without deleting any data, run

```bash
./src/sh/db/local_db_stop.sh
```

To completely destroy this local database, and delete its data, secrets etc., use

```bash
./src/sh/db/local_db_destroy.sh
```

## Setting up a dev database on a Kubernetes cluster

First set up the [kubectl](/prod/kubernetes/README.md) and [helm](/prod/helm/README.md) CLIs.

Then run

```bash
./src/sh/db/dev_db_setup.sh
```

This will:

1. Ensure the existence of a Kubernetes `Namespace` with the name of the user running this script.
2. Create a release from a PostgreSQL helm chart in this namespace.
3. Set up logical databases on this release.

To completely destroy this release, and delete its data, secrets etc., use

```bash
./src/sh/db/dev_db_destroy.sh
```

This will not destroy the namespace.

## Database creds

To facilitate creds rotation, each production logical database has an owner role and login role, as
described [here](/src/python/toolchain/util/db/README.md). For uniformity, we use this scheme even
with dev databases.

The setup scripts mentioned above create these roles and store the login role creds for each logical database,
as well as master creds for the entire instance, as secrets.  For a local db the secrets will be stored
locally (under `~/.toolchain_secrets_dev/`). For a dev db on Kubernetes, the secrets will be stored
as Kubernetes `Secret` resources in your namespace.

## Migrations

The [`migrate.sh`](migrate.sh) script runs migrations on all logical databases.

In the presence of multiple databases, Django is finicky about running migrations in a specific order.
This script does the right thing, so you don't need to think about it.

This is called by the db setup scripts, so you don't usually neeed to run it directly.
However, if you create new migrations for any database, re-run this script to apply them.

## Bootstaping the DEV Database

The [`bootstrap_dev_db.sh`](bootstrap_dev_db.sh) script creates a Toolchain customer and repo and adds a Django superuser.

This is called by the db setup scripts, so you don't usually need to run it directly.
