# Toolchain Frontend

This section of the repository is where the code for Toolchain's web frontend lives. The
assets built by this project are output to the `servicerouter` static directory.
We use [NVM](https://github.com/nvm-sh/nvm) to manage nodejs versions (using .nvmrc files), and [yarn](https://yarnpkg.com/) as our package manager.

## Running a local dev server

To start a localhost development server:

In the `src/node/toolchain/frontend` directory, run:

```shell
yarn start
```

Upon the first run, this will spend
a bit of time building the web fronted assets, serve them at `localhost:8080`, and open
up a page in the default web browser pointing to `localhost:8080`.

## Running backends

In order for web requests made by the localhost javascript to return
meaningful data, it is also necessary to proxy these commands to the dev cluster.
We do this by running a kubernetes command that spawns a server at `localhost:9500`,
which proxies requests made against `localhost:8080` to the cluster.

If you want to develop against backends running on the dev cluster under your own namespace:

In the root of the toolchain repository, run:

```shell
./src/sh/kubernetes/port_forward.sh servicerouter
```

To develop against backends running under some other namespace:

In the root of the toolchain repository, run:

```shell
kubectl --namespace NAMESPACE port-forward service/servicerouter 9500:80
```

Once this is running, it will be necessary to access `localhost:9500` in a web browser
and authenticate against the dev backend, before proxying from the node development
server will work correctly.

You might also want to run a backend locally. For each backend you want to run locally:

In the root of the toolchain repository, run:

```shell
./src/python/toolchain/service/servicerouter/manage.py BACKEND
```

Backend names are defined in [the service router urls config](../../../python/toolchain/servicerouter/urls.py).

## Additional scripts

See the `scripts` key in the root `package.json` file for additional build-related scripts that can
be run with `yarn run <scriptname>`.

## Building/bundling files

In `src/node/toolchain/frontend`:

```shell
yarn build
```

Files are generated in `dist/spa/servicerouter/generated/`

## Running tests

In `src/node/toolchain/frontend`:

```shell
yarn test
```

We make use of [Jest snapshots](https://jestjs.io/docs/en/snapshot-testing) in order to test the web UI. To
update these snapshots:

In `src/node/toolchain/frontend`:

```shell
yarn run test --updateSnapshot
```

## Deploying to dev environments

Manually make sure that the node packages installed are up to date with the yarn.lock file by running `yarn install` from the `src/node` folder.

```shell
yarn install --dev
```

When running in our dev Kubernetes cluster our service router service (which serves the SPA) will try to read the current version of the SPA in dev (based on the Kubernetes namespace).
To build & deploy a new SPA version to a dev environment use the `deploy_toolchain_spa_dev` script:

```shell
 ./src/python/toolchain/prod/installs/deploy_toolchain_spa_dev.py deploy --namespace=asher
```

In this example the SPA is deployed to the service router running in the "asher" namespace.
Note: the deploy script will also restart the service router web server (gunicorn) to trigger reloading the new deployed version.

## Deploying to staging & production

Before deploying make sure that the node packages installed are up to date with the yarn.lock file by running `yarn install` from the `src/node` folder.

```shell
yarn install --dev
```

Deploying to production is a two step process. First you deploy to staging, and test the SPA there. If the SPA works as expected the next step is to promote that version from staging to production.

To build, upload & deploy a version to staging run:

```shell
 ./src/python/toolchain/prod/installs/deploy_toolchain_spa_prod.py stage
```

You must run this script on a clean & merged branch, the script will check that the current git commit is the most recent master branch commit. Otherwise it won't run.
This script will build the bundles, upload them to s3, create a manifest and for the version (also in s3) and will update the version pointer file for the staging environment (namespace) to point to the new version (via manifest).
Finally it will trigger the reload of the service router web server (gunicorn) so it will start serving the new version.

Once the version is ready to go to production run:

```shell
 ./src/python/toolchain/prod/installs/deploy_toolchain_spa_prod.py promote
```

This will update the version pointer file for the production environment (namespace) to point the the version that the staging environment currently points to.
