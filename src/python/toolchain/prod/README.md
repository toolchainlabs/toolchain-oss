# Tools descriptions

This directory contains Python scripts related to creating and running services.

## curl.py

The [`curl.py`](curl.py) script wraps `curl` for calling app.toolchain.com/api/v1 to first obtain
the necessary access token using an already-obtained refresh token, and then invokes `curl`
with the `Authorization` header set appropriately.

For example, to query <https://app.toolchain.com/api/v1/packagerepo/pypi/modules/?q=requests==2.23.0>',
run it like this:

```bash
./src/python/toolchain/prod/curl.py '/packagerepo/pypi/modules/?q=requests==2.23.0'
```

## ensure_ecr_repo.py

The [`ensure_ecr_repo.py`](ensure_ecr_repo.py) script creates the ECR repo for a
service's image.  You only need to call it once, when creating a new service.

Run it like this:

```bash
./src/python/toolchain/prod/ensure_ecr_repo.py --service=my/service/name
```

## ensure_k8s_service_role.py

The [`ensure_k8s_service_role.py`](ensure_k8s_service_role.py) script creates an IAM role
for a given service to assume when running in a given cluster.
You only need to call it once, when creating a new service.

Run it like this:

```bash
./src/python/toolchain/prod/ensure_k8s_service_role.py --cluster=k8s-cluster-name --service=my/service/name
```

Any extra permissions a service might need are attached to the relevant role via [Terraform config](/prod/terraform/resources/us-east-1/kubernetes).

## rotate_jwt_secrets.py

The [`rotate_jwt_secrets.py`](rotate_jwt_secrets.py) script creates and/or rotates JWT keys used to sign &  verify JWT.

To create or rotate the secrets on your local machine, run

```shell
./src/python/toolchain/prod/rotate_jwt_secrets.py --local
```

To create the secrets in a dev namespace (defaults to the current user's namespace)

```shell
./src/python/toolchain/prod/rotate_jwt_secrets.py --dev-namespaces <namespace>
```

To rotate secrets in prod:

```shell
./src/python/toolchain/prod/rotate_jwt_secrets.py --prod
```

Note that in "prod" mode this script will update secrets in multiple namespaces (prod & staging) on multiple clusters (production & remoting clusters)

## ensure_secrets.py

The [`ensure_secrets.py`](ensure_secrets.py) script creates the
[secrets](/src/python/toolchain/util/secret/README.md) required to run Django services during development.

To create the secrets on your local machine, run

```shell
./src/python/toolchain/prod/ensure_secrets.py --local
```

To create the secrets in a namespace on a particular cluster, run

```shell
./src/python/toolchain/prod/ensure_secrets.py --cluster <cluster> --namespaces <namespace>
```

Omitting the namespace while specifying the dev cluster will default to your dev namespace, which is named for your username:

```shell
./src/python/toolchain/prod/ensure_secrets.py --cluster dev-e1-1
```

This script is idempotent and can be run safely multiple times.

The secrets it creates are:

### The Django SECRET_KEY

All Django apps require a "secret key", used to encrypt cookies etc.
No persistent data is encrypted with this key, so losing it is more of an
inconvenience (e.g., all sessions would be invalidated) than a disaster.

### GitHub OAuth credentials

Allows our users service to authenticate users via their GitHub accounts.
We actually have two sets of GitHub OAuth creds, one for dev and one for prod.
The `./src/python/toolchain/prod/ensure_secrets.py` script always gets the dev creds.
