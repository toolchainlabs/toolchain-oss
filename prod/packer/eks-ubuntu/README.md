# EKS Node Image for Ubuntu 20.04 LTS

## Building

Run the following command with Packer v1.6.x or higher to build the AMI:

```shell
cd prod/packer/eks-ubuntu
packer build .
```

## Notes

This config differs from the official AWS config as follows:

- The config uses the HCL (Hashicorp Configuration Language) form of Packer configs instead of the older
  JSON format configs.

- `yum` commands have been replaced by equivalent `apt-get` commands. The
  [Nexus357ZA/ubuntu-eks-ami](https://github.com/Nexus357ZA/ubuntu-eks-ami) repository was helpful here.

- The ability to configure additional yum repositories has been removed (or as would be the case for this
  config, additional apt repositories). The scripts `scripts/cleanup_additional_repos` and
  `scripts/install_additional_repos` from the AWS configs have been deleted.

- The config install v2 of the AWS CLI tool directly from the official release instead of the older v1
  available through PyPi.

- The config does not install the Cloud Formation helper scripts. I've left the relevant commands commented out
  for now (as I intend to open source this config).

- The Docker version is just whatever is in the Ubuntu repository and cannot be configured like it can be
  in the official EKS Packer config. (We may want to add back this feature so we can freeze the config at a
  known version.)

- The cleanup code in the official EKS Packer config deletes /etc/resolv.conf which should not be done on
  Ubuntu as that file is not dynamically-generated like it is on Amazon Linux 2.
  
- The VPC and subnet filter are specific to Toolchain's infrastructure.

## Sources / Updating

### Files

This Packer config relies heavily on the [Packer config for official AWS EKS AMI](https://github.com/awslabs/amazon-eks-ami).
Most of the files in the [`files` directory](files/) are vendored from that official AMI. Run the `update.sh` script
in this directory to download the most recent copies.

This config also uses the Ubuntu EKS AMI configs at <https://github.com/Nexus357ZA/ubuntu-eks-ami> for the
changes to the [`install-worker.sh` script](scripts/install-worker.sh) necessary to get the script to run
on the Debian-based Ubuntu (versus the Red Hat-based Amazon Linux 2 used in the official AMI).

### EKS Versions

To see latest EKS builds, run `aws --region=us-west-2 s3 ls s3://amazon-eks/`. To see latest Kubernetes build dates
for a version, run a command with the version like: `aws --region=us-west-2 s3 ls s3://amazon-eks/1.17.9/`. Then
update the appropriate entries in `versions.pkr.hcl`.
