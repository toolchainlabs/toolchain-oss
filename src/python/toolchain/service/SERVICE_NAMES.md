# Service Names

The _name_ of a Toolchain Django-based service is the relative path, from this directory, to the directory
containing its settings.py, manage.py and so on.

E.g., `infosite`, `users`, `buildsense/api`, `toolshed`, `crawler/pypi/worker` etc.

We use this name as an argument to various build scripts.  These script expect various other paths to
conform to this naming scheme.

Specifically, for a service `foo/bar`:

- The `pex_binary` target for the service's gunicorn entry point should be
  `src/python/toolchain/service/foo/bar:foo-bar-gunicorn`.
- The ECR repo for this entry point's images should be named `foo/bar/gunicorn`.
- The Helm chart for deploying this service should be at `prod/helm/foo/bar`

Some scripts can also take a path prefix of a service, and act on all services found under that prefix.

E.g., `somescript.sh buildsense` will act on `buildsense/api` and `buildsense/workflow`.

## Support for service groups

To make it easier and less error prone to run scripts that deal with multiple services (mostly build and deploy scripts), a service group can also be specified.
Use the `%` (percent) sign to indicate you are using a group name as opposed to a service name/root.

A service can be a part of multiple groups, a service's group membership is defined in the [services.json](../config/services.json) file.

## Implementation

The logic to extrapolate services based on tree structure or group names is implemented in an `extrapolate_services` function.
