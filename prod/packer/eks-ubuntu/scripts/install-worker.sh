#!/usr/bin/env bash
# Copyright 2022 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

set -o pipefail
set -o nounset
set -o errexit
IFS=$'\n\t'

TEMPLATE_DIR=${TEMPLATE_DIR:-/tmp/worker}

################################################################################
### Validate Required Arguments ################################################
################################################################################
validate_env_set() {
    (
        set +o nounset

        if [ -z "${!1}" ]; then
            echo "Packer variable '$1' was not set. Aborting"
            exit 1
        fi
    )
}

validate_env_set BINARY_BUCKET_NAME
validate_env_set BINARY_BUCKET_REGION
validate_env_set CNI_PLUGIN_VERSION
validate_env_set KUBERNETES_VERSION
validate_env_set KUBERNETES_BUILD_DATE
validate_env_set PULL_CNI_FROM_GITHUB

################################################################################
### Machine Architecture #######################################################
################################################################################

MACHINE=$(uname -m)
if [ "$MACHINE" == "x86_64" ]; then
    ARCH="amd64"
elif [ "$MACHINE" == "aarch64" ]; then
    ARCH="arm64"
else
    echo "Unknown machine architecture '$MACHINE'" >&2
    exit 1
fi

################################################################################
### Packages ###################################################################
################################################################################

# Disable automatic Apt updates.
sudo systemctl stop apt-daily.timer
sudo systemctl stop apt-daily.service
sudo systemctl kill --kill-who=all apt-daily.service
sudo systemctl disable apt-daily.service # disable run when system boot
sudo systemctl disable apt-daily.timer   # disable timer run
sudo systemctl mask apt-daily.service
sudo systemctl daemon-reload

# wait until `apt-get updated` has been killed
while ! (systemctl list-units --all apt-daily.service | grep -E -q '(dead|failed)')
do
  sleep 1
done

# Update the OS to begin with to catch up to the latest packages.
sudo DEBIAN_FRONTEND=noninteractive apt-get update -y
sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

sudo DEBIAN_FRONTEND=noninteractive apt-get -y install software-properties-common
sudo DEBIAN_FRONTEND=noninteractive apt-add-repository -y universe
sudo DEBIAN_FRONTEND=noninteractive apt-get -y update

# Install necessary packages
sudo DEBIAN_FRONTEND=noninteractive apt-get -y install \
     chrony \
     conntrack \
     curl \
     gpg \
     jq \
     nfs-common \
     socat \
     unzip \
     wget

# Install AWS CLI
ls -lR "${TEMPLATE_DIR}"
gpg --import "${TEMPLATE_DIR}/awscli-gpg-public-key.txt"
curl --fail -L -o awscliv2.zip "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip"
curl --fail -L -o awscliv2.sig "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip.sig"
if ! gpg --verify awscliv2.sig awscliv2.zip ; then
  echo "ERROR: awscli: gpg failed to verify the integrity of the awscli archive" 1>&2
  exit 1
fi
unzip ./awscliv2.zip
sudo ./aws/install
/usr/local/bin/aws --version
rm -rf aws awscliv2.sig awscliv2.zip

# Install Cloud Formation helper scripts.
# https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/cfn-helper-scripts-reference.html
#sudo DEBIAN_FRONTEND=noninteractive apt-get -y install python3-pip
#sudo -H pip3 install https://s3.amazonaws.com/cloudformation-examples/aws-cfn-bootstrap-latest.tar.gz
#sudo ln -s /root/aws-cfn-bootstrap-latest/init/ubuntu/cfn-hup /etc/init.d/cfn-hup

################################################################################
### Time #######################################################################
################################################################################

# Make sure Amazon Time Sync Service starts on boot.
sudo systemctl enable chrony

# Make sure that chronyd syncs RTC clock to the kernel.
cat <<EOF | sudo tee -a /etc/chrony.conf
# This directive enables kernel synchronisation (every 11 minutes) of the
# real-time clock. Note that it can’t be used along with the 'rtcfile' directive.
rtcsync
EOF

# If current clocksource is xen, switch to tsc
if grep --quiet xen /sys/devices/system/clocksource/clocksource0/current_clocksource &&
  grep --quiet tsc /sys/devices/system/clocksource/clocksource0/available_clocksource; then
    echo "tsc" | sudo tee /sys/devices/system/clocksource/clocksource0/current_clocksource
else
    echo "tsc as a clock source is not applicable, skipping."
fi

################################################################################
### DNS ########################################################################
################################################################################

# Symlink /etc/resolv.conf to /run/systemd/resolve/resolv.conf to disable the
# systemd stub resolver. Otherwise, this will cause coredns to see a DNS loop
# which causes it to error exit forever.
#
# See:
# - https://coredns.io/plugins/loop/#troubleshooting-loops-in-kubernetes-clusters
# - man page for systemd-resolved(8):
#   "Note that the selected mode of operation for this file is detected fully automatically, depending
#    on whether /etc/resolv.conf is a symlink to /run/systemd/resolve/resolv.conf or lists 127.0.0.53 as
#    DNS server."

sudo rm -f /etc/resolv.conf
sudo ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf

################################################################################
### iptables ###################################################################
################################################################################

echo iptables-persistent iptables-persistent/autosave_v4 boolean true | sudo debconf-set-selections
echo iptables-persistent iptables-persistent/autosave_v6 boolean true | sudo debconf-set-selections

sudo DEBIAN_FRONTEND=noninteractive apt install -y -q iptables-persistent netfilter-persistent

sudo ufw default allow incoming
sudo ufw default allow outgoing

sudo bash -c "/sbin/iptables-save > /etc/iptables/rules.v4"
sudo netfilter-persistent save

sudo mv "${TEMPLATE_DIR}/iptables-restore.service" /etc/systemd/system/iptables-restore.service

sudo systemctl daemon-reload
sudo systemctl enable iptables-restore


################################################################################
### Docker #####################################################################
################################################################################

sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg-agent \
    software-properties-common

INSTALL_DOCKER="${INSTALL_DOCKER:-true}"
if [[ "$INSTALL_DOCKER" == "true" ]]; then
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -

    sudo apt-key fingerprint 0EBFCD88

    sudo add-apt-repository \
       "deb [arch=amd64] https://download.docker.com/linux/ubuntu \
       $(lsb_release -cs) \
       stable"

    sudo DEBIAN_FRONTEND=noninteractive apt-get update

    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
         docker-ce \
         docker-ce-cli \
         containerd.io

    sudo usermod -aG docker "$USER"

    sudo mkdir -p /etc/docker
    sudo mv "${TEMPLATE_DIR}/docker-daemon.json" /etc/docker/daemon.json
    sudo chown root:root /etc/docker/daemon.json

    # Enable docker daemon to start on boot.
    sudo systemctl daemon-reload
    sudo systemctl enable docker
fi

################################################################################
### Logrotate ##################################################################
################################################################################

# kubelet uses journald which has built-in rotation and capped size.
# See man 5 journald.conf
sudo mv "${TEMPLATE_DIR}/logrotate-kube-proxy" /etc/logrotate.d/kube-proxy
sudo mv "${TEMPLATE_DIR}/logrotate.conf" /etc/logrotate.conf
sudo chown root:root /etc/logrotate.d/kube-proxy
sudo chown root:root /etc/logrotate.conf
sudo mkdir -p /var/log/journal

################################################################################
### Kubernetes #################################################################
################################################################################

sudo mkdir -p /etc/kubernetes/manifests
sudo mkdir -p /var/lib/kubernetes
sudo mkdir -p /var/lib/kubelet
sudo mkdir -p /opt/cni/bin

echo "Downloading binaries from: s3://$BINARY_BUCKET_NAME"
S3_DOMAIN="amazonaws.com"
if [ "$BINARY_BUCKET_REGION" = "cn-north-1" ] || [ "$BINARY_BUCKET_REGION" = "cn-northwest-1" ]; then
    S3_DOMAIN="amazonaws.com.cn"
fi
S3_URL_BASE="https://$BINARY_BUCKET_NAME.s3.$BINARY_BUCKET_REGION.$S3_DOMAIN/$KUBERNETES_VERSION/$KUBERNETES_BUILD_DATE/bin/linux/$ARCH"
S3_PATH="s3://$BINARY_BUCKET_NAME/$KUBERNETES_VERSION/$KUBERNETES_BUILD_DATE/bin/linux/$ARCH"

BINARIES=(
    kubelet
    aws-iam-authenticator
)
for binary in ${BINARIES[*]} ; do
    if [[ -n "${AWS_ACCESS_KEY_ID:-}" ]]; then
        echo "AWS cli present - using it to copy binaries from s3."
        aws s3 cp --region "${BINARY_BUCKET_REGION}" "${S3_PATH}/${binary}" .
        aws s3 cp --region "${BINARY_BUCKET_REGION}" "${S3_PATH}/${binary}.sha256" .
    else
        echo "AWS cli missing - using wget to fetch binaries from s3. Note: This won't work for private bucket."
        sudo wget "${S3_URL_BASE}/${binary}"
        sudo wget "${S3_URL_BASE}/${binary}.sha256"
    fi
    sudo sha256sum -c "${binary}.sha256"
    sudo chmod +x "$binary"
    sudo mv "$binary" /usr/bin/
done

# Since CNI 0.7.0, all releases are done in the plugins repo.
CNI_PLUGIN_FILENAME="cni-plugins-linux-${ARCH}-${CNI_PLUGIN_VERSION}"

if [ "$PULL_CNI_FROM_GITHUB" = "true" ]; then
    echo "Downloading CNI plugins from GitHub"
    wget "https://github.com/containernetworking/plugins/releases/download/${CNI_PLUGIN_VERSION}/${CNI_PLUGIN_FILENAME}.tgz"
    wget "https://github.com/containernetworking/plugins/releases/download/${CNI_PLUGIN_VERSION}/${CNI_PLUGIN_FILENAME}.tgz.sha512"
    sudo sha512sum -c "${CNI_PLUGIN_FILENAME}.tgz.sha512"
    rm "${CNI_PLUGIN_FILENAME}.tgz.sha512"
else
    if [[ -n "$AWS_ACCESS_KEY_ID" ]]; then
        echo "AWS cli present - using it to copy binaries from s3."
        aws s3 cp --region "$BINARY_BUCKET_REGION" "${S3_PATH}/${CNI_PLUGIN_FILENAME}.tgz" .
        aws s3 cp --region "$BINARY_BUCKET_REGION" "${S3_PATH}/${CNI_PLUGIN_FILENAME}.tgz.sha256" .
        sudo sha256sum -c "${CNI_PLUGIN_FILENAME}.tgz.sha256"
    else
        echo "AWS cli missing - using wget to fetch cni binaries from s3. Note: This won't work for private bucket."
        sudo wget "${S3_URL_BASE}/${CNI_PLUGIN_FILENAME}.tgz"
        sudo wget "${S3_URL_BASE}/${CNI_PLUGIN_FILENAME}.tgz.sha256"
    fi
fi
sudo tar -xvf "${CNI_PLUGIN_FILENAME}.tgz" -C /opt/cni/bin
rm "${CNI_PLUGIN_FILENAME}.tgz"

sudo rm ./*.sha256

sudo mkdir -p /etc/kubernetes/kubelet
sudo mkdir -p /etc/systemd/system/kubelet.service.d
sudo mv "${TEMPLATE_DIR}/kubelet-kubeconfig" /var/lib/kubelet/kubeconfig
sudo chown root:root /var/lib/kubelet/kubeconfig
sudo mv "${TEMPLATE_DIR}/kubelet.service" /etc/systemd/system/kubelet.service
sudo chown root:root /etc/systemd/system/kubelet.service
sudo mv "${TEMPLATE_DIR}/kubelet-config.json" /etc/kubernetes/kubelet/kubelet-config.json
sudo chown root:root /etc/kubernetes/kubelet/kubelet-config.json


sudo systemctl daemon-reload
# Disable the kubelet until the proper dropins have been configured
sudo systemctl disable kubelet

################################################################################
### EKS ########################################################################
################################################################################

sudo mkdir -p /etc/eks
sudo mv "${TEMPLATE_DIR}/eni-max-pods.txt" /etc/eks/eni-max-pods.txt
sudo mv "${TEMPLATE_DIR}/bootstrap.sh" /etc/eks/bootstrap.sh
sudo chmod +x /etc/eks/bootstrap.sh

################################################################################
### AMI Metadata ###############################################################
################################################################################

BASE_AMI_ID=$(curl -s  http://169.254.169.254/latest/meta-data/ami-id)
cat <<EOF > /tmp/release
BASE_AMI_ID="$BASE_AMI_ID"
BUILD_TIME="$(date)"
BUILD_KERNEL="$(uname -r)"
ARCH="$(uname -m)"
EOF
sudo mv /tmp/release /etc/eks/release
sudo chown -R root:root /etc/eks

################################################################################
### Stuff required by "protectKernelDefaults=true" #############################
################################################################################

cat <<EOF | sudo tee -a /etc/sysctl.d/99-amazon.conf
vm.overcommit_memory=1
kernel.panic=10
kernel.panic_on_oops=1
EOF

################################################################################
### Cleanup ####################################################################
################################################################################

# Clean up APT caches to reduce the image size
sudo DEBIAN_FRONTEND=noninteractive apt-get -y autoremove --purge
sudo DEBIAN_FRONTEND=noninteractive apt-get -y clean
sudo DEBIAN_FRONTEND=noninteractive apt-get -y autoclean

sudo rm -rf "$TEMPLATE_DIR"

# Clean up files to reduce confusion during debug
sudo rm -rf \
    /etc/hostname \
    /etc/machine-id \
    /etc/ssh/ssh_host* \
    /home/ubuntu/.ssh/authorized_keys \
    /root/.ssh/authorized_keys \
    /var/lib/cloud/data \
    /var/lib/cloud/instance \
    /var/lib/cloud/instances \
    /var/lib/cloud/sem \
    /var/lib/dhclient/* \
    /var/lib/dhcp/dhclient.* \
    /var/log/cloud-init-output.log \
    /var/log/cloud-init.log \
    /var/log/secure \
    /var/log/wtmp

sudo touch /etc/machine-id
