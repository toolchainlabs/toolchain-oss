# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

# Useful links:
# https://packer.io/guides/automatic-operating-system-installs/preseed_ubuntu.html
# https://github.com/boxcutter/ubuntu/blob/master/script/update.sh
# https://github.com/fasmat/ubuntu

source "virtualbox-iso" "ubuntu2004" {
  iso_url = "http://releases.ubuntu.com/focal/ubuntu-20.04.3-live-server-amd64.iso"
  iso_checksum = "f8e3086f3cea0fb3fefb29937ab5ed9d19e767079633960ccb50e76153effc98"
  guest_os_type = "Ubuntu_64"

  boot_wait = "5s"
  boot_command = [
    " <wait>",
    " <wait>",
    " <wait>",
    " <wait>",
    " <wait>",
    "<esc><wait>",
    "<f6><wait>",
    "<esc><wait>",
    "<bs><bs><bs><bs><wait>",
    " autoinstall<wait5>",
    " ds=nocloud-net<wait5>",
    ";s=http://<wait5>{{.HTTPIP}}<wait5>:{{.HTTPPort}}/<wait5>",
    " ---<wait5>",
    "<enter><wait5>"
  ]

  memory = 4096
  cpus = 4
  disk_size = 102400

  http_directory = "./http" # serves the user-data config

  communicator = "ssh"
  ssh_username = "vagrant"
  ssh_password = "vagrant"
  ssh_wait_timeout = "10000s"
  ssh_handshake_attempts = "100"

  virtualbox_version_file = ".vbox_version"
  guest_additions_path = "VBoxGuestAdditions_{{.Version}}.iso"

  shutdown_command = "echo 'vagrant' | sudo -S shutdown -P now"
}
