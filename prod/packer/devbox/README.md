# Devbox Image

This directory contains [Packer](https://packer.io) configurations to build a Toolchain development
environment for various systems. We currently support building AMI images for AWS EC2 and a
[Vagrant](https://www.vagrantup.com/) "box" that runs via VirtualBox.

Note: Packer v1.6.0 or higher is required.

## AMI

To build the AMI, run:

```bash
cd prod/packer/devbox
packer build -only amazon-ebs* .
```

This will startup an EC2 instance and run the AMI build. The ID of the AMI will be output to the console
when the build completes. You will then need to rebuild the devbox using the new AMI *including copying
over any existing home directories to avoid data loss*. Note: The existing Terraform configuration always
uses the latest available devbox AMI so there is no need to update any AMI ID in the Terraform config.

## Vagrant

### First-time setup

1. Install [VirtualBox](https://www.virtualbox.org/).

2. Install [Vagrant](https://www.vagrantup.com/).

   * macOS: Run `brew cask install vagrant` to install via Homebrew.

### Building the image

Build `toolchain-ubuntu2004.box` by running:

   ```shell
   cd prod/packer/devbox
   packer build -only virtualbox*2004 .
   ```

### Publishing the image to Vagrant Cloud

1. Publish the box to Vagrant Cloud by setting `VERSION` to the version you are publishing and then running:

   ```shell
   VERSION=x.y.z  # replace with the version you are publishing
   vagrant cloud version create toolchain/devbox $VERSION
   vagrant cloud provider create toolchain/devbox virtualbox $VERSION
   vagrant cloud provider upload toolchain/devbox virtualbox $VERSION toolchain-ubuntu2004.box
   ```

   You may see an error about `exit code: 52` and `Empty reply from server`. This seems to be an issue with Vagrant
   Cloud side where it receives the upload just fine but reports this error. Verify the upload by checking
   [the web interface for the box](https://app.vagrantup.com/toolchain/boxes/devbox) and see if the version
   of the box is ready to be released.

2. Release the box by running: `vagrant cloud version release toolchain/devbox $VERSION`

3. Bump the box version in [`Vagrantfile`](../../../Vagrantfile). Submit a PR with that change.

## Developing & Debugging

### Generally

* To dump Packer's logs to a file, add `PACKER_LOG=1 PACKER_LOG_PATH=run.log` before the `packer` invocation to dump
all of Packer's logs to `run.log` (or whatever other filename you choose).

* See the [Packer debugging documentation](https://www.packer.io/docs/debugging) for useful tips and tricks
  including:
  
  * Use the `-debug` option to have Packer pause between each step invocation. For AWS AMI builds, Packer will also
    output a SSH key into the local directory to use to access the EC2 instance.

  * USe the `-on-error=ask` option to have Packer prompt whether to continue should a test step fail. (This gives
    you the opportunity to inspect the template VM before you signal Packer to continue or stop.)

### AWS

* Use the `-debug` option to put Packer into debug mode. Packer will write a SSH key into a `.pem` file in the
current directory. For example, debug mode for this devbox config writes the SSH key to `ec2_ubuntu1804.pem`
which can then be used to access the template EC2 instance by running: `ssh -i ec2_ubuntu1804.pem ubuntu@HOST`

  * Copy files to the template EC2 instance by running: `scp -i ec2_ubuntu1804.pem SOURCE_FILE ubuntu@HOST:DEST_FILE`

* You can test out an AMI once it is built by using it to instantiate an EC2 instance. The [Terraform devbox
  module](../../terraform/modules/devbox) takes an `ami_override` parameter that can be used to set the AMI
  used to instantiate a devbox.
  
### Vagrant

* Once `toolchain-ubuntu2004.box` has been produced, you can test it out locally by adding it to Vagrant before the
  upload/release process described earlier.

  * To add the box, run: `vagrant box add --name=foo toolchain-ubuntu2004.box`
  * Then create an empty directory with a `Vagrantfile` in that directory with this content:

    ```hcl
    Vagrant.configure("2") do |config|
      config.vm.box = "foo"
    end
    ```

  * Then run `vargrant up` in that directory to start the VM.
