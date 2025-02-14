# Python based Services composition &  boilerplate

This directory contains per-service boilerplate.

This helps us enforce the sometimes-fuzzy distinction between a Django app and a service
(a "project" in Django parlance.)

## Django Terminology

A _Django app_ is just a Python package that provides some set of Django-related functionality, such as models, views,
templates, static files, etc. Apps may be reused in various projects.

A _Django project_ is a runnable web application, composed of one or more apps.  A project is primarily defined
by a `settings.py` file containing its settings, but it will usually also have the various files needed to define
entry points and url paths, such as `gunicorn_main.py`, `gunicorn_conf.py`, `urls.py` and so on.

It's common, especially in simpler django projects, for the project files to live within the primary app related
to that project. This unfortunately creates confusion between the two concepts.
See [here](https://docs.djangoproject.com/en/2.2/ref/applications/) for more details.

## Toolchain Service Projects

Many of our services are implemented as Django projects, and their project-level files live under this directory
instead of under any app. This helps enforce and clarify that these are services composed of multiple apps, and
those apps exist independently of any specific service that happens to use them.

## Service Names

See [here](SERVICE_NAMES.md) for important information about how services are referenced in various scripts.

## Running Dev Services Locally

It's often useful to run a service on your laptop, while developing and debugging.

To do so run

```shell
./src/python/toolchain/service/<service name>/manage.py runserver
```

E.g.,

```shell
./src/python/toolchain/service/buildsense/api/manage.py runserver
```

This will run a local instance of the service on its [dev port](../django/util/DEV_PORTS.md).

See [here](../../../../prod/helm/README.md) for how to run dev services on Kubernetes.

### Secrets in dev

Some services require [secrets](../../../../util/secrets/README.md), there are a few scripts that handle & manage those.

- DB Secrets are created & destroyed by the [scripts used to setup and destroy databases](../../../sh/db/README.md).
- JWT keys are managed by the [rotate_jwt_secrets script](../prod/README.md#rotate_jwt_secretspy)
- All other secrets (django secrets, github app secrets, etc...) are managed by the [ensure_secrets.py script](../prod/README.md#ensure_secretspy)

## Generating Service Boilerplate

There is a helper script for generating boilerplate for a new service.

To use it, first update the [service list](../config/services.json) with the info for your service.

Then run:

```shell
./src/python/toolchain/django/util/generate_service_boilerplate.py --service-name=my/foo/service
```

Then update the generated files as indicated.

The `_jinja2` directories [here](./_jinja2) and under [prod/helm](../../../../prod/helm/base/_jinja2) contain
the templates used by this generator script.

## Ensuring Service Setup

After updating the  [service list](../config/services.json) with the info for your new service, you can run

```shell
./src/python/toolchain/prod/ensure_service_setup.py
```

to ensure the existence of various production resources required by the service. Specifically:

- The ECR repo for the service's gunicorn image.
- The IAM role to be assumed by the service on each Kubernetes cluster.
