# CI

## Overview

We use CircleCI for continuous integration.

Links:

- [CircleCI UI for toolchain repo](https://app.circleci.com/pipelines/github/toolchainlabs/toolchain)
- [CI config](../.circleci/config.yml)

## Docker Image

See the [CI image README](../prod/docker/ci/README.md) for details on the Docker image used in CI.

## CircleCI Environment Variables

The following environment variables are set in
[the CircleCI UI](https://app.circleci.com/settings/project/github/toolchainlabs/toolchain) to control CI execution:

- `TOOLCHAIN_AUTH_TOKEN`
  - Authentication token to use to access [Buildsense](https://app.toolchain.com/).
- `TOOLCHAIN_DISABLE_REMOTE_CACHE`
  - If set, then remote caching will be disabled.

## Rotating AWS Credentials

We have an IAM user that the Circle CI jobs use in order to access AWS resources (mostly access Terraform State in DynamdoDB and S3).
We set the IAM user's access key & secert (credentials) as environment variable so the code running in the CI job can access those AWS resources.
From time to time we roate those keys.
Follow these steps:

- Go to the [IAM console](https://console.aws.amazon.com/iam/home#/users/circleci?section=security_credentials) and generate a new key.
- Go to the Circle CI setting organization page under context select the [`aws` context](https://app.circleci.com/settings/organization/github/toolchainlabs/contexts/4335ce9c-cee5-4ffb-8cc3-ee81f2c0ef02?return-to=https%3A%2F%2Fapp.circleci.com%2Fpipelines%2Fgithub%2Ftoolchainlabs%2Ftoolchain)
- Set the `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` environment variable to the new credentials generated in the AWS IAM console.
- After a few CI jobs run, make sure the `last used` value on the new key is updated and the old key is no longer used.
- Deactivate and delete the old key.
