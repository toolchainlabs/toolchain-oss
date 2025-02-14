# Terraform

The [Terraform](https://www.terraform.io/) configurations for our production environment.

A working knowledge of the Terraform configuration language and commands is helpful for understanding
these files.

The [modules](modules) subdir contains reusable configuration modules, e.g., "a postgres db".

The [resources](resources) subdir contains configuration for concrete resources, e.g., "the postgres db
used by the crawler in us-east-1". Most concrete resources are  implemented using one or more modules
from [modules](modules).

Terraform config lives in `.tf` files, but note that the contents of all `.tf` files in a directory are a
single unit, as if they were in a single file.

## Updating Terraform versions

Hashicorp [release new versions of Terraform](https://github.com/hashicorp/terraform/releases) on a regular basis, typically every few weeks.
It is worth noting that running a newer version of terraform locally in order to apply state (i.e. `terraform apply`) while our [CI image](../docker/ci/README.md#terraform) uses an earlier version of terraform will cause CI builds to fail.
The reason is that when CI runs it reads our terraform state from AWS S3 (where we store it) and it checks the version of terraform that wrote this state.

If it sees a detects that a version the the one currently running has modified state, it will fail and exit, causing our CI builds to break.
Therefore, before running terraform locally, check the version (`terraform version`) and make sure it is the same version we run in CI.
If not, refer to this [README](../docker/ci/README.md) and update the terraform version first.

## Parameterization of Terraform config

For Terraform config to be useful, it has to support re-use, which requires parameterization.

There are three possible sources of parameter values for a terraform resource:

- Input variables.
- Remote AWS state.
- Remote Terraform state.

### Input Variables

These are defined, by convention, in a module's `variables.tf` file. E.g.,

```hcl
variable "vpc_id" {
  description = "The VPC for the crawler instance."
}
```

Variable values must be provided when instantiating the module:

```hcl
module "clusters" {
  source = "../../workflow/clusters"
  vpc_id = var.vpc_id
  ...
}
```

Variables tightly couple Terraform resources to each other: There is no way to obtain the `vpc_id` until
the VPC has been created, so you are guaranteed that it exists when the `clusters` config is applied to create
clusters.

Note that only modules may have variables. Concrete resources are intended to require no further input.

### Remote AWS State

This is determined by querying AWS. E.g.,

```hcl
# Data source to read attributes of the general-use private network.
data "aws_subnet" "private" {
  vpc_id = var.vpc_id
  filter {
    name = "tag:Name"
    values = ["private"]
  }
}
```

In this example, the config assumes that the given VPC has a subnet with the name `private`, and that this
subnet has the expected properties (i.e., cannot be accessed from the public internet).

Remote state represents loose coupling: The VPC exists (we have its id), but the subnet is merely assumed to have
been provided by some other, already-applied Terraform config; There is no guarantee that it has been.
If it does not exist, the query, and thus the application of this config, will fail.

### Remote Terraform State

We use Terraform [remote state](https://www.terraform.io/docs/state/remote.html), so that
the source of truth about deployed resources and their mappings to Terraform config
lives in one canonical place. That place is the S3 bucket `terraform.toolchainlabs.com`.
The corresponding locks live in the Dynamo DB table of the same name. These are both in
region `us-west-2`, unrelated to whichever region Terraform is deploying in.
Which is why you'll see stanzas like this, with the hard-coded region, in resource
(but not module) config:

```hcl
terraform {
  backend "s3" {
    bucket = "terraform.toolchainlabs.com"
    key = "state/us-east-1/vpc"
    region = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}
```

The S3 key for state created by some config is `state/<PATH>` where `<PATH>` is that config dir's path
relative to the [resources](resources) dir. E.g., the state for resources whose config is in
`prod/terraform/resources/us-east-1/vpc` is under the key `state/us-east-1/vpc`, as you can see
[here](resources/us-east-1/vpc/vpc.tf).  Note that although this is state for a resource in `us-east-1`, the
state itself lives in `us-west-2`, where all our remote state, for all regions, lives.

It is possible, in a config file, to query this remote state:

```hcl
# Data source to fetch the name of the AWS region we're operating in.
data "aws_region" "current" {}

# Data source to read remote state for one-per-region resources.
data "terraform_remote_state" "region" {
  backend = "s3"
  config {
    bucket = "terraform.toolchainlabs.com"
    key = "state/${data.aws_region.current.name}/region"
    region = "us-west-2"
    dynamodb_table = "terraform.toolchainlabs.com"
  }
}
```

And then use it, e.g.,

```hcl
resource "aws_iam_role_policy_attachment" "general_bucket_readwrite" {
  role = "${aws_iam_role.cluster_role.name}"
  policy_arn = "${data.terraform_remote_state.region.s3_general_bucket_readwrite_arn}"
}
```

This, again, represents loose coupling, but it's more brittle than querying AWS state, because it
implies knowledge of the structure of other config, rather than just assumptions about the results
of the application of that other config. So we try to avoid overuse of remote state querying.

In modules, we currently allow querying of remote state only for `state/global` (global state) and
`state/${region_name}/region` (one-per-region state), as those don't change much.

In resources, we allow querying of more specific resource state, but only from sibling resources.
E.g., the crawler service config may query the crawler db config to get the ARN of the policy that
grants access to the db's credentials in secretsmanager.

## Design Note

We currently break up both our modules and our configurations into multiple, relatively fine-grained projects.
The advantage of this decoupling is the ability to work with frequently-changing infrastructure,
such as EKS nodes, without requiring Terraform to laboriously evaluate the unchanging
parts, such as VPCs and databases, which would require large numbers of AWS API roundtrips
and can significantly slow things down.

So, for example, the project that manages an EKS cluster can receive information about its VPC
and DB either from input variables, by querying AWS state or by querying remote Terraform state,
but it does not know about them from statically-determined dependencies.

It also gets complicated to introduce static dependencies between repeatable components
(e.g., databases) and components that can only exist once per region (e.g., a KMS key with
a given name) or once globally (e.g., an AWS service-linked role).  Ways around this include
having multiple copies of essentially the same component, differing only by name, but that
isn't ideal. Separating projects resolves this in a neater way.

However, the disadvantage of this decoupling is that Terraform can only do component dependency analysis
at the planning stage via static dependencies, i.e., within a single project. So, for example, a
change to a database will not know that it has to trigger corresponding changes to an ECS cluster
that depends on that database, much less apply them in the right order.

This means that the operator must consider the cross-project impact of changes, and act accordingly.
E.g., quiescing an EKS cluster before making VPC changes. Note that cross-project dependencies
*are* available dynamically at apply time (either from input variables or from querying remote state).
E.g., when re-applying the EKS cluster configuration, it will notice that the VPC has changed
in the remote state. It just cannot know this at the planning stage, before the VPC has actually changed.

The `terraform_all.sh` scripts in [resources](resources) help manage this decoupling. See there for details.

It is much easier to merge projects than it is to split them, so we start with this fine granularity,
and can change it later if the disadvantages listed above become significant.
