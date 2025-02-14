# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Useful links:
# https://packer.io/guides/automatic-operating-system-installs/preseed_ubuntu.html
# https://github.com/boxcutter/ubuntu/blob/master/script/update.sh

source "virtualbox-iso" "ubuntu1804" {
  vm_name = "ubuntu1804"
  iso_url = "http://cdimage.ubuntu.com/releases/18.04.4/release/ubuntu-18.04.4-server-amd64.iso"
  iso_checksum = "e2ecdace33c939527cbc9e8d23576381c493b071107207d2040af72595f8990b"
  guest_os_type = "Ubuntu_64"

  # Taken from https://github.com/chef/bento/blob/master/packer_templates/ubuntu/ubuntu-18.04-amd64.json
  boot_command = [
    "<esc><wait>",
    "<esc><wait>",
    "<enter><wait>",
    "/install/vmlinuz<wait>",
    " auto<wait>",
    " console-setup/ask_detect=false<wait>",
    " console-setup/layoutcode=us<wait>",
    " console-setup/modelcode=pc105<wait>",
    " debconf/frontend=noninteractive<wait>",
    " debian-installer=en_US.UTF-8<wait>",
    " fb=false<wait>",
    " initrd=/install/initrd.gz<wait>",
    " kbd-chooser/method=us<wait>",
    " keyboard-configuration/layout=USA<wait>",
    " keyboard-configuration/variant=USA<wait>",
    " locale=en_US.UTF-8<wait>",
    " netcfg/get_domain=vm<wait>",
    " netcfg/get_hostname=vagrant<wait>",
    " grub-installer/bootdev=/dev/sda<wait>",
    " noapic<wait>",
    " preseed/url=http://{{ .HTTPIP }}:{{ .HTTPPort }}/preseed.cfg<wait>",
    " -- <wait>",
    "<enter><wait>",
  ]

  memory = 4096
  cpus = 4
  disk_size = 102400

  http_directory = "./http" # serves the preseed.cfg config

  communicator = "ssh"
  ssh_username = "vagrant"
  ssh_password = "vagrant"
  ssh_wait_timeout = "10000s"

  vboxmanage = [
    [ "modifyvm", "{{.Name}}", "--nictype1", "virtio" ],
  ]

  virtualbox_version_file = ".vbox_version"
  guest_additions_path = "VBoxGuestAdditions_{{.Version}}.iso"

  shutdown_command = "echo 'vagrant' | sudo -S shutdown -P now"
}
