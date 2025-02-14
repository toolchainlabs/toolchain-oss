# Toolchain Frontend

This section of the repository is where the code for Pants demo site web app lives. The
assets built by this project are output to the `build` directory.
We use [NVM](https://github.com/nvm-sh/nvm) to manage nodejs versions (using .nvmrc files), and [yarn](https://yarnpkg.com/) as our package manager.

## Running a local dev server

To start a localhost development server:

In the `src/node/toolchain/pants-demo-site` directory, run:

```shell
yarn start
```

Upon the first run, this will spend
a bit of time building the web fronted assets, serve them at `localhost:3000`, and open
up a page in the default web browser pointing to `localhost:3000`.

## Running backends

In order for web requests made by the localhost javascript to return
meaningful data, it is also necessary to proxy these commands to the dev cluster.
We do this by running a kubernetes command that spawns a server at `localhost:9050`,
which proxies requests made against `localhost:3000` to the cluster.

In the root of the toolchain repository, run:

```shell
./src/sh/kubernetes/port_forward.sh servicerouter
```

You can access the server side pages on `localhost:9050`.

## Additional scripts

See the `scripts` key in the root `package.json` file for additional build-related scripts that can
be run with `yarn run <scriptname>`.

## Building/bundling files

In `src/node/toolchain/pants-demo-site`:

```shell
yarn build
```

Files are generated in `src/node/toolchain/pants-demo-site/build`

## Running unit tests

In `src/node/toolchain/pants-demo-site`:

```shell
yarn test
```

## Running browser tests with cypress

In `src/node/toolchain/pants-demo-site`:

```shell
yarn start
```

Once the app is running, in a second terminal window run:

```shell
yarn cypress-test
```