# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

build {
  sources = [
    "source.amazon-ebs.ubuntu1804",
  ]

  # Issue: EC2 Nitro-based instances ignore the disk name defined in the EC2 instance's block device mapping.
  # The drives are named after the non-deterministic order in which the kernel found them. The original
  # device name is stored in the vendor data returned by the NVMe disk controller's identify command.
  #
  # See https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/nvme-ebs-volumes.html#identify-nvme-ebs-device
  # for more information.
  #
  # The following three files implement udev rules to extract the disk name from the NVMe controller vendor data
  # and create stable symlinks for the disk. The files are taken from an Amazon Linux 2 system.

  provisioner "file" {
    source = "scripts/70-ec2-nvme-devices.rules"
    destination = "/tmp/70-ec2-nvme-devices.rules"  # scripts/aws-specific.sh will move to final location
  }

  provisioner "file" {
    source = "scripts/ebsnvme-id"
    destination = "/tmp/ebsnvme-id"  # scripts/aws-specific.sh will move to final location
  }

  provisioner "file" {
    source = "scripts/ec2nvme-nsid"
    destination = "/tmp/ec2nvme-nsid"  # scripts/aws-specific.sh will move to final location
  }

  # Install the GPG public key used to verify the integrity of awscli archives.
  provisioner "file" {
    source = "scripts/awscli-gpg-public-key.txt"
    destination = "/tmp/awscli-gpg-public-key.txt"
  }

  provisioner "shell" {
    scripts = [
      "scripts/packages.sh",
      "scripts/aws-specific.sh",
      "scripts/toolchain.sh",
    ]
  }
}

build {
  sources = [
    "source.virtualbox-iso.ubuntu1804",
    "source.virtualbox-iso.ubuntu2004",
  ]

  # Setup vagrant-specific configurations, e.g. enable root access for the vagrant user,
  # and upgrade system packages.
  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
      "SSH_USERNAME=vagrant",
      "SSH_PASSWORD=vagrant",
    ]

    execute_command = "echo 'vagrant' | {{.Vars}} sudo -E -S bash '{{.Path}}'"
    expect_disconnect = true

    scripts = [
      "scripts/vagrant.sh",
      "scripts/update.sh",
    ]
  }

  # Force reboot so any upgraded kernel is now running.
  provisioner "shell" {
    execute_command = "echo 'vagrant' | {{.Vars}} sudo -E -S bash '{{.Path}}'"
    expect_disconnect = true
    script = "scripts/reboot.sh"
  }

  # Install VirtualBox Guest Additions into the VM.
  provisioner "shell" {
    execute_command = "echo 'vagrant' | {{.Vars}} sudo -E -S bash '{{.Path}}'"
    script = "scripts/virtualbox.sh"
  }

  # Force reboot again to ensure the VirtualBox Guest Additions are running.
  provisioner "shell" {
    execute_command = "echo 'vagrant' | {{.Vars}} sudo -E -S bash '{{.Path}}'"
    expect_disconnect = true
    script = "scripts/reboot.sh"
  }

  # Install the GPG public key used to verify the integrity of awscli archives.
  provisioner "file" {
    source = "scripts/awscli-gpg-public-key.txt"
    destination = "/tmp/awscli-gpg-public-key.txt"
  }

  # Provision Toolchain-specific resources into the devbox.
  # Note: These scripts are able to access root via `sudo`.
  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
    ]

    scripts = [
      "scripts/packages.sh",
      "scripts/toolchain.sh",
      "scripts/adjust-vagrant-account.sh",
    ]
  }

  # Cleanup the image.
  provisioner "shell" {
    environment_vars = [
      "DEBIAN_FRONTEND=noninteractive",
    ]

    execute_command = "echo 'vagrant' | {{.Vars}} sudo -E -S bash '{{.Path}}'"

    scripts = [
      "scripts/cleanup.sh",
    ]
  }

  post-processor "vagrant" {
    output = "toolchain-ubuntu2004.box"
  }
}
