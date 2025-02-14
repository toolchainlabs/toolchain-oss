# Devbox

## Background

The devbox provides a Toolchain development environment within AWS. The devbox is instantiated from a custom
EC2 AMI [image built with Packer](../prod/packer/devbox/README.md).

## Prerequisites

Set up Bastion. See [here](../prod/python/toolchain_prod/scripts/BASTION.md).

Confirm that you added `ForwardAgent yes` to your laptop's `~/.ssh/config`.

## First login to devbox

1. Login to the devbox by first accessing the bastion and then ssh'ing to the devbox:

   * Login to bastion: `ssh bastion.toolchain.private`

   * Then login from the bastion to the devbox: `ssh devbox.toolchain.private`

   * Note: The login attempt will fail the first time while `keymaker` creates an account for you. Hit Ctrl-C to
   exit out of that first `ssh` and then run your ssh command again. This will occur for both the login to
   the bastion and the login to the devbox.

   * Pro Tip: Add the following to your `~/.ssh/config` to enable automatic "proxy jump" through the
   bastion:

   ```config
   Host *.toolchain.private *.ec2.internal !bastion.toolchain.private
      ProxyJump bastion.toolchain.private
   ```

2. In the shell where you are running `ssh`, you should enable the SSH Agent so that your SSH private key
   can be usable by the devbox for GitHub access. The SSH agent will not expose the private key to the devbox.
   Run the following in that shell:

   ```shell
   eval $(ssh-agent)
   ssh-add
   ```

3. Setup `pyenv` for your devbox account by running: `pyenv install 3.9.12 && pyenv global 3.9.12`

4. Copy your AWS configuration from your laptop to the devbox:

   On devbox:

   ```shell
   mkdir ~/.aws
   ```

   On laptop (assuming ProxyJump is configured):

   ```shell
   scp ~/.aws/* devbox.toolchain.private:.aws/
   ```

5. Follow the [general repository setup instructions](../SETUP.md) to clone and setup your Toolchain clone.  
