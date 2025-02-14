# Terraform at Toolchain

Terraform config for our concrete AWS resources.

## Running Terraform Commands

To facilitate working with multiple projects, we introduce the `terraform_all.sh` wrapper scripts.
Each such script recursively runs `terraform_all.sh` in any direct subdir that has that script, and runs
`terraform` in any direct subdir that doesn't. The `terraform_all.sh` scripts thus encode the order
in which to run Terraform across projects.  To view this order, simply look at the source for that script.

So, for example, to initialize all projects, run `terraform_all.sh init` in this dir.
To initialize just the crawler in `us-east-1`, run the same command in the `us-east-1/crawler-e1-1`.
To initialize just the vpc in `us-east-1`, run `terraform init` in `us-east-1/vpc`, as that
dir is a leaf dir, so it has no `terraform_all.sh` script.

See the subdir README.md files for more details on each project.

## Upgrading providers

Since Terraform introduced lock files we leverage those, however those make upgrading version a multi-step process.
The script `upgrade_providers.sh` contains the set of commands needed to upgrade provides.
