# Kubernetes at Toolchain

We use [Kubernetes](https://kubernetes.io/) to run our apps/services in dev and in prod (you can still run most things locally on you laptop).
Our Kubernetes clusters are managed clusters using [AWS EKS](https://aws.amazon.com/eks/) so a combination of IAM polices and Kubernetes config maps are used to control access to the clusters.

We run 3 clusters, all in AWS US-EAST-1 region:

- Development environments - dev-e1-1
- Production web app - prod-e1-1
- Production remoting (for remote cache and eventually remote execution) - remoting-prod-e1-1

## The Kubernetes CLI

The Kubernetes CLI, `kubectl`, allows you to query and modify the state of a cluster.

See below for how to install it and set it up.

## Contexts

`kubectl` can have multiple named _contexts_. In our case we create one context per cluster, named for the cluster.

Every `kubectl` command can be run in a given context (i.e., a given cluster) with the `--context` flag,
e.g., `--context dev-e1-1`.

See below for how to set up a context for a cluster in your CLI.

You can list all contexts with ```kubectl config get-contexts```

You can also set a _current_ context, and `kubectl` will use that if the `--context` flag isn't provided.

You can view the current context with ```kubectl config current-context``` and set it with
```kubectl config use-context <context name>```

You typically want to have the dev cluster be the current (and usually only!) context for your CLI:

```kubectl config use-context dev-e1-1```

## Namespaces

On a single cluster, resources are partitioned into namespaces.

Every `kubectl` command can be run against a given namespace with the `--namespace` flag, e.g., `--namespace dev`

You can list all namespaces with ```kubectl get namespaces```

You can also set a _current_ namespace for the context, and `kubectl` will use that if the `--namespace` flag
isn't provided.

You can view the current namespace in each context with ```kubectl config view``` and set it with
```kubectl config set-context <context name> --namespace=<namespace>```

On the dev cluster, you have a personal namespace, named as your toolchain username.  You typically want this
to be the current namespace for the dev cluster's context:

```kubectl config set-context dev-e1-1 --namespace=<mytoolchainusername>```

If your Kubernetes CLI is set up as outlined above, your `kubectl` commands that don't specify `--context`
or `--namespace` will default to your personal namespace on the dev cluster.

See below for how to set up this personal namespace on the dev cluster.

## Logging in to the Kubernetes Dashboard

Kubernetes has a nifty browser-based dashboard.  To access it:

Run `kubectl proxy` to port-forward from `localhost` to the dashboard.

Obtain a token via [`src/sh/kubernetes/dashboard_login_token_gen.sh`](../../src/sh/kubernetes/dashboard_login_token_gen.sh).

Visit [the login url](http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:https/proxy/#/login)
and paste in token generated from step 1.

If you run the `dashboard_login_token_gen.sh` script with `-o` or `--open` it will open that URL for you in a browser.

## Setting up the Kubernetes CLI

Note: On macOS, our homebrew setup will install the following tools so you don't have to install them manually. On
Linux though, you will need to do the following:

- [Install the `aws` CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-install.html).

- [Install `kubectl` CLI](https://kubernetes.io/docs/tasks/tools/install-kubectl/).

- [Install `aws-iam-authenticator`](https://docs.aws.amazon.com/eks/latest/userguide/install-aws-iam-authenticator.html)
and place it on your `$PATH`.

## Setting up Kubernetes CLI Cluster Context

### Adding You As a Cluster User

You will need to be added to the `aws-auth` ConfigMap in Kubernetes by someone who is already an administrator:

- Modify the configmap for the cluster you need access to.
  a clause for yourself in the `mapUsers` key. You can obtain your user's ARN by running `aws sts get-caller-identity`
  if you already have setup an AWS access key. (The ARN is generally in the form `arn:aws:iam::283194185447:user/<USER>`
  where `<USER>` is your username.)
  - [Dev cluster](./configs/dev-e1-1/auth/aws_users_config_map.yaml)
  - [Web app production cluster](./configs/prod-e1-1/auth/aws_users_config_map.yaml)
  - [Remoting production cluster](./configs/remoting-prod-e1-1/auth/aws_users_config_map.yaml)

- Submit and land a PR with that change.

- Once it lands on master, ask someone who is already an administrator to run the apply script (located in the same directory as the yaml config map file, under prod/kubernetes/configs)

(For more, see the `EKS` docs for [adding a user role](https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html)).

### Add the Cluster Context to your Kubernetes CLI

Configure `kubectl` to add a context for the given cluster:

```prod/kubernetes/kubectl_setup.sh <cluster_name>```

Specifically, to add a context for the dev cluster:

```prod/kubernetes/kubectl_setup.sh dev-e1-1```

This script will:

- Create a context for the given cluster, using your local AWS credentials.
- Configure `kubectl` to use the cluster's context by default.

### Create Your Personal Namespace

Run:

```prod/kubernetes/dev_namespace_setup.sh <cluster_name>```

Specifically, for the dev cluster:

```prod/kubernetes/dev_namespace_setup.sh dev-e1-1```

This script will:

- Create a namespace, named for your username, on the cluster. You can use this namespace for experimenting
  without affecting other developers.
- Configure `kubectl` to default to your namespace.

### Setting up A Context For the Prod Cluster

To add a context for the prod cluster in your Kubernetes CLI (only do this if you have good reason to!):

```prod/kubernetes/kubectl_setup.sh prod-e1-1```

But then be sure to run ```kubectl config use-context dev-e1-1``` so that your default context remains the dev cluster!

### Port Forwarding

Working with Kubernetes both in prod and dev involves the process of [port forwarding](https://kubernetes.io/docs/tasks/access-application-cluster/port-forward-access-application-cluster/) to make various services running in Kubernetes available local host.
Typing the kubernetes port forward command can become repetitive and cumbersome. A UI tool like [Kube Forwarder](https://kube-forwarder.pixelpoint.io/) can help with this.

## Updating images (AMIs) for Kubernetes nodes

Periodically, AWS will [release new AMIs](https://github.com/awslabs/amazon-eks-ami/releases) to use with Kubernetes nodes.
We uses managed EKS nodes groups so nodes can be rolled out gradually by AWS EKS via the AWS EKS console. see: <https://docs.aws.amazon.com/eks/latest/userguide/update-managed-node-group.html>
