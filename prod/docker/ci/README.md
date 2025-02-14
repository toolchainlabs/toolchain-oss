# CI Image

## Building a new image

1. Run `prod/docker/ci/build.sh` in this directory. This will build a new image and output a new tag. This should
look like `283194185447.dkr.ecr.us-east-1.amazonaws.com/ci:2020-03-03.23-05-12-8aa726f829b8`.

2. Iterate on the image until you are ready to deploy it. Then get the changes to `prod/docker/ci/Dockerfile`
landed on master via a PR. In that PR, also change `prod/docker/remoting/buildbox_run/Dockerfile.toolchainlabs` for our remote execution worker image.

## Deploying the image

1. The changes to `prod/docker/ci/Dockerfile` and `prod/docker/remoting/buildbox_run/Dockerfile.toolchainlabs` should have already been approved and landed on the `master` branch.

2. On the [devbox](../../../docs/devbox.md), build the production version of the images by running `prod/docker/ci/build.sh` from master and `prod/docker/remoting/buildbox_run/build_toolchain_public.sh`. This will ensure that the tags incorporate the SHA of the `master` branch commit.

3. Update `default_image` in `.circleci/config.yml` with the new CI tag.

4. Update `build_buildbox_workers_ecs.py` with the remote execution tag.

5. Run `src/sh/ci/ensure-toolchain-image.sh`. This will update the tag in`.envrc.ci-image`.

6. Land a PR with those changes and then the image will be enabled on master.
