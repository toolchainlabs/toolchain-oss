#!/bin/bash
# Copyright 2020 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -xeo pipefail

# Dependency versions and sha256 checksums.

amazon_ecr_credential_helper_version=0.5.0
amazon_ecr_credential_helper_sha256="a0ae9a66b1f41f3312785ec5e17404c7fd2a16a35703c9ea7c050406e20fc503"

git_lfs_version=3.0.1
git_lfs_sha256="cf640836e0207a896da76c6ddf2f7612b22e021876091f836b6f4ccf16c8e470"

golang_version=1.17.1
golang_sha256="dab7d9c34361dc21ec237d584590d72500652e7c909bf082758fb63064fca0ef"

helm_version=3.7.0
helm_sha256="096e30f54c3ccdabe30a8093f8e128dba76bb67af697b85db6ed0453a2701bf9"

kubectl_version=1.22.2 # from https://storage.googleapis.com/kubernetes-release/release/stable.txt
kubectl_sha256="aeca0018958c1cae0bf2f36f566315e52f87bdab38b440df349cd091e9f13f36"

# note: sha256 is for the packer.zip archive, not the `packer` binary
packer_version=1.7.6
packer_sha256="d2717af4d728cd9034c7a3bb2c6eac384d772bae78d856413b14742a0ca28a1c"

# note: sha256 is for the terraform.zip archive, not the `terraform` binary
terraform_version=1.0.7
terraform_sha256="bc79e47649e2529049a356f9e60e06b47462bf6743534a10a4c16594f443be7b"

umoci_version=0.4.7
umoci_sha256="6abecdbe7ac96a8e48fdb73fb53f08d21d4dc5e040f7590d2ca5547b7f2b2e85"

yq_version=4.13.2
yq_sha256="d7c89543d1437bf80fee6237eadc608d1b121c21a7cbbe79057d5086d74f8d79"


# Append a line to a file as root. Necessary to call bash this way since this script runs as `ubuntu` and the
# output redirection would otherwise fail with a permission denied error.
function append_line_root() {
  sudo /bin/bash -c "echo '$2' >> \"$1\""
}

# Additional packages for Toolchain-repo required software
sudo apt-get install -y \
  direnv \
  jq

# Create work directory for software downloads.
WORK_DIR="${HOME}/init-workspace"
mkdir -p "$WORK_DIR"
cd "$WORK_DIR"

bashrc_template_file="/etc/skel/.bashrc"
append_line_root "$bashrc_template_file" ""
append_line_root "$bashrc_template_file" '# *** TOOLCHAIN EDITS BELOW THIS LINE'

# pyenv
git clone https://github.com/pyenv/pyenv.git /tmp/pyenv.git
sudo mkdir -p /usr/local/opt/pyenv
sudo tar cvf - -C /tmp/pyenv.git . | sudo tar xf - -C /usr/local/opt/pyenv
sudo /bin/bash -c "cat >> \"${bashrc_template_file}\"" <<'EOF'
# Enable pyenv (installing it to home directory if not already installed).
export PYENV_ROOT="${HOME}/.pyenv"
if [ ! -d "${PYENV_ROOT}" ]; then
  mkdir "${PYENV_ROOT}"
  cp -r /usr/local/opt/pyenv/. "${PYENV_ROOT}"
  echo -e '\033[32mFIRST LOGIN: Please setup Pyenv by running: pyenv install 3.9.12 && pyenv global 3.9.12\033[39m'
fi
export PATH="${PYENV_ROOT}/bin:${PATH}"
eval "$(pyenv init -)"

EOF

## Setup direnv.
# shellcheck disable=SC2016
append_line_root "$bashrc_template_file" 'eval "$(direnv hook bash)"'

# Go
curl --fail -L -o go.tar.gz "https://dl.google.com/go/go${golang_version}.linux-amd64.tar.gz" && \
  echo "${golang_sha256}  go.tar.gz" | sha256sum -c -
sudo mkdir -p /usr/local/go /usr/local/bin
sudo tar xzvf go.tar.gz -C /usr/local/go --strip-components=1
sudo ln -s /usr/local/go/bin/go /usr/local/bin/go
sudo ln -s /usr/local/go/bin/gofmt /usr/local/bin/gofmt

# yq
curl --fail -L -o ./yq "https://github.com/mikefarah/yq/releases/download/v${yq_version}/yq_linux_amd64" && \
  echo "${yq_sha256}  yq" | sha256sum -c -
sudo mv yq /usr/local/bin/yq
sudo chmod 555 /usr/local/bin/yq
sudo chown root:root /usr/local/bin/yq

# terraform
curl --fail -L -o ./terraform.zip "https://releases.hashicorp.com/terraform/${terraform_version}/terraform_${terraform_version}_linux_amd64.zip" && \
  echo "${terraform_sha256}  terraform.zip" | sha256sum -c -
unzip ./terraform.zip
sudo mv ./terraform /usr/local/bin/terraform
sudo chmod 555 /usr/local/bin/terraform
sudo chown root:root /usr/local/bin/terraform

# packer
curl --fail -L -o ./packer.zip "https://releases.hashicorp.com/packer/${packer_version}/packer_${packer_version}_linux_amd64.zip" && \
  echo "${packer_sha256}  packer.zip" | sha256sum -c -
unzip ./packer.zip
sudo mv ./packer /usr/local/bin/packer
sudo chmod 555 /usr/local/bin/packer
sudo chown root:root /usr/local/bin/packer

# kubectl
curl --fail -L -o ./kubectl "https://storage.googleapis.com/kubernetes-release/release/v${kubectl_version}/bin/linux/amd64/kubectl" && \
  echo "${kubectl_sha256}  kubectl" | sha256sum -c -
chmod +x ./kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
sudo chmod 555 /usr/local/bin/kubectl
sudo chown root:root /usr/local/bin/kubectl

# helm
curl --fail -L -o helm-linux-amd64.tar.gz "https://get.helm.sh/helm-v${helm_version}-linux-amd64.tar.gz" && \
  echo "${helm_sha256}  helm-linux-amd64.tar.gz" | sha256sum -c -
mkdir helm
tar xzvf ./helm-linux-amd64.tar.gz -C helm
sudo mv helm/linux-amd64/helm /usr/local/bin/helm
sudo chmod 555 /usr/local/bin/helm
sudo chown root:root /usr/local/bin/helm

# AWS CLI
gpg --import /tmp/awscli-gpg-public-key.txt
rm /tmp/awscli-gpg-public-key.txt
curl --fail -L -o awscliv2.zip "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
curl --fail -L -o awscliv2.sig "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip.sig"
if ! gpg --verify awscliv2.sig awscliv2.zip ; then
  echo "ERROR: awscli: gpg failed to verify the integrity of the awscli archive"
  exit 1
fi
unzip ./awscliv2.zip
sudo ./aws/install

# Enable core dumps.
echo '* soft core unlimited' | sudo tee -a /etc/security/limits.d/50-unlimited-core-dumps.conf
echo '* hard core unlimited' | sudo tee -a /etc/security/limits.d/50-unlimited-core-dumps.conf
echo 'kernel.core_pattern=/tmp/core-%e.%p.%h.%t' | sudo tee -a /etc/sysctl.d/99-core-dump-pattern.conf
# Apport overwrites the core pattern when it starts: see https://unix.stackexchange.com/a/563505
sudo apt-get -y remove apport

# git (most recent stable)
sudo add-apt-repository -y ppa:git-core/ppa
sudo apt-get update
sudo apt-get -y install git

# git-lfs
curl --fail -L -o git-lfs_amd64.deb "https://packagecloud.io/github/git-lfs/packages/debian/buster/git-lfs_${git_lfs_version}_amd64.deb/download" && \
  echo "${git_lfs_sha256}  git-lfs_amd64.deb" | sha256sum -c -
sudo apt-get install -y ./git-lfs_amd64.deb

# OCI utilities: podman, skopeo
# shellcheck disable=SC1091
. /etc/os-release
sudo /bin/bash -c "echo 'deb https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_${VERSION_ID}/ /' > /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list"
curl --fail -L "https://download.opensuse.org/repositories/devel:kubic:libcontainers:stable/xUbuntu_${VERSION_ID}/Release.key" | sudo apt-key add -
sudo apt-get update
sudo apt-get -y install podman skopeo

# OCI utility: umoci
curl --fail -L -o umoci.amd64 "https://github.com/opencontainers/umoci/releases/download/v${umoci_version}/umoci.amd64" && \
  echo "${umoci_sha256}  umoci.amd64" | sha256sum -c -
sudo mv umoci.amd64 /usr/local/bin/umoci
sudo chmod 555 /usr/local/bin/umoci
sudo chown root:root /usr/local/bin/umoci

# docker-credential-ecr-login
curl --fail -L -o ./docker-credential-ecr-login https://amazon-ecr-credential-helper-releases.s3.us-east-2.amazonaws.com/${amazon_ecr_credential_helper_version}/linux-amd64/docker-credential-ecr-login && \
  echo "${amazon_ecr_credential_helper_sha256}  docker-credential-ecr-login" | sha256sum -c -
sudo mv ./docker-credential-ecr-login /usr/local/bin/docker-credential-ecr-login
sudo chmod 555 /usr/local/bin/docker-credential-ecr-login
sudo chown root:root /usr/local/bin/docker-credential-ecr-login

# docker-compose
# use PyPi since Ubuntu's version is too old to support the features we use
sudo /usr/bin/pip3 install docker-compose

# bazel
curl --fail -L https://bazel.build/bazel-release.pub.gpg | sudo apt-key add -
echo "deb [arch=amd64] https://storage.googleapis.com/bazel-apt stable jdk1.8" | sudo tee /etc/apt/sources.list.d/bazel.list
sudo apt-get update
sudo apt-get -y install bazel

# Remove the work directory as the last step.
rm -rf "$WORK_DIR"
