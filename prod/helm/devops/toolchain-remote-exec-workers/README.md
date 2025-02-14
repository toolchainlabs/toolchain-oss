# Remote Execution Workers Chart

We use this chart to deploy Remote Execution workers serving the [Toolchain repo](https://github.com/toolchainlabs/toolchain) into our [Kubernetes dev cluster dev-e1-1](https://us-east-1.console.aws.amazon.com/eks/home?region=us-east-1#/clusters/dev-e1-1).
The image used by this deployment is defined and built by the docker file & script in the [remoting worker directory](../../../docker/remoting/worker_scie/).
Currently the image is published into our public AWS ECR registry (no need to do that anymore, and this will be updated soon).
Even though this workload is intended for the dev cluster, it connects to our production environment (grpcs://workers.toolchain.com) and serves our production remote execution workload, meaning remote execution request coming from pants running in CircleCI.
