# Docker files

Contains Dockerfiles for building our various docker images, and
various config files that those Dockerfiles reference.

The Dockerfiles expect to be built in the context of our entire source
repo (minus some ignored dirs, see [.dockerignore](/.dockerignore) in the repo root).

## Building Django-based Services

### Building Gunicorn Images

Our Django-based services (e.g., infosite, users, buildsense, crawler) are built by running

```shell
./prod/docker/build.sh <service name or prefix>
```

See [SERVICE_NAMES.md](../../src/python/toolchain/service/SERVICE_NAMES.md) for details.

This script will build a docker image whose entrypoint is the service's gunicorn server,
push the new image to the appropriate ECR repo, and print its tag to the console.
Then you can use that tag in service configs to pick up that image on the next deploy.

### Building the nginx Image

Django-based services that serve over HTTP are deployed with a sidecar nginx that handles
incoming requests, serves static files and proxies dynamic page requests to the gunicorn.

This image doesn't need to be built very often, but when it does, simply run

```shell
./prod/docker/build_nginx.sh
```

This script will build the nginx docker image, push the new image to the appropriate ECR repo,
and print its tag to the console. Then you can use that tag in service configs to pick up that
image on the next deploy.

## Other Docker Images

We also have Dockerfiles and associated build scripts for building the image we run CI jobs in.
See those subdirectories for more details.
