# End 2 End at Toolchain

## General

We leverage helm's [test release](https://helm.sh/docs/topics/chart_tests/#steps-to-run-a-test-suite-on-a-release) to run end 2 end test against a service once it is deployed.

Our build, install & deploy support end 2 end testing in several ways:

* [build & publish docker images](../../src/python/toolchain/prod/builders/e2e_tests_builder.py) containing tests as part of the build process.
* Set the correct image tag for the e2e tests so they can propagate to the helm templates defining the tests.
* Running the tests - after a release was installed
* Collect test results, show them to the user (console), and include them in the deploy email.
* [future] collect logs and other artifacts from the test and attach them to the deploy email/show them to the user.

## Writing tests

Tests can be really anything that can run in a container running in Kubernetes.
[init containers](https://kubernetes.io/docs/concepts/workloads/pods/init-containers/) can be used to setup the run environment for the test.

In the remote cache proxy end 2 end test, we run a tool to [create JWT access tokens](../../src/python/toolchain/prod/e2e_tests/setup_jwt_keys.py) that uses the JWT keys (secrets) to create an access token, store it on a volume, and have the [CasLoad](https://github.com/toolchainlabs/remote-api-tools#load-testing) use that access token when it runs.

For python services we write tests using [pytest](https://pytest.org/).
As a convention we put those tests in an `e2e_tests` folder under the service composition directory.

Currently we have:

* [info site tests](../../src/python/toolchain/service/infosite/e2e_tests)
* [webhooks service tests](../../src/python/toolchain/service/webhooks/e2e_tests)

note that there is "special" code in the BUILD file to prevent Pants's default behavior of treating those test files (and conftest.py) as unit tests, from a pants perspective, those are not tests since we treat them as a python library, package them into a pex file, and ship them in a container in order to run them in Kubernetes.

Using pytest hooks & fixtures allows us to pass command line arguments (to indicate Kubernetes and toolchain env) so the test con be configured to run against the correct environment.
