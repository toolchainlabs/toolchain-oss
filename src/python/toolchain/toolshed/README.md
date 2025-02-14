# Toolshed -  back office admin service

This service provides a single point where we can use web UI and django management commands to manage and operate the various microservices that comprise the Toolchain service.

## Features

* Access [Django Admin Web UI](https://toolshed.toolchainlabs.com/db/users/admin/) for all databases.
* Run DB migrations from this service's manage.py
* Access [DB Views](https://toolshed.toolchainlabs.com/db/pypi/dbz/) for [locks](https://toolshed.toolchainlabs.com/db/pypi/dbz/locks/), [explain](https://toolshed.toolchainlabs.com/db/pypi/dbz/explain/), etc.
* Access [Workflow Admin Web UI](https://toolshed.toolchainlabs.com/db/pypi/workflow/summary/).

## Accessing the service

In dev & production, authenticating to the Toolshed service is done via GitHub and Duo for 2FA.
 See [VPN docs](../../../../prod/VPN.md) for details about onboarding into Duo.

### In production

You will need to be connected to the [VPN](../../../../prod/VPN.md) in order to access the service.
Login via GitHub, after passing login you will be redirected to our [Duo](https://duo.com) 2FA authentication page.

### In dev

Access is done by port forwarding the toolshed service from the dev cluster to the local machine.
This can be done by using the Kubernetes port forwarding helper script:

```shell
 ./src/sh/kubernetes/port_forward.sh toolshed
```

* Note that the script relies on current Kubernetes context and namespace (those can be viewed by running `kubectl config get-contexts`)

Login via GitHub. After passing login, you will be redirected to our [Duo](https://duo.com) 2FA authentication page.

## Granting access to toolshed

A user must be promoted by an existing staff user to staff status via the [Toolshed Users DB Admin UI](https://toolshed.toolchainlabs.com/db/users/admin/site/toolchainuser/?is_active__exact=1).

Only Toolchain employees that belong to the toolchain org (customer) are eligible to be promoted and granted access to toolshed.

Note that in dev, the [bootstrap script](../users/management/commands/bootstrap.py) grants staff access to the user, this script runs as part of the DB setup process in dev (local or on k8s).
