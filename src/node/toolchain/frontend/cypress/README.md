# End 2 End tests using cypress

## Interactive tests runner ()

* [cypress studio](https://docs.cypress.io/guides/core-concepts/cypress-studio#Using-Cypress-Studio)
from `src/node/toolchain/frontend` run:

```shell
 node_modules/.bin/cypress open
```

## Running from CLI

[cypress run](https://docs.cypress.io/guides/guides/command-line#cypress-run-spec-lt-spec-gt)

from `src/node/toolchain/frontend` run:

```shell
node_modules/.bin/cypress run  --spec cypress/integration/infosite/infosite.js
```

[with environment variables](https://docs.cypress.io/guides/guides/environment-variables#Option-4-env) (required by tests):

```shell
node_modules/.bin/cypress run --env INFOSITE_LINK="https://toolchain.com" --spec cypress/integration/infosite/infosite.js
```

## Running in Docker

```shell
docker run -it -v $PWD/src/node/toolchain/frontend/:/e2e -w /e2e cypress/included:7.3.0
```
