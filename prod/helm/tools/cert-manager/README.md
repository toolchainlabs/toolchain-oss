# cert-manager

## Why cert-manager?

[cert-manager](https://cert-manager.io/) automates the issuance and renewal of TLS certificates.
To quote its website, cert-manager introduces "certificate authorities and certificates as first-class
resource types in the Kubernetes API."

We use cert-manager as part of managing TLS certificates in instances (such as Buildfarm) where
we are terminating TLS for ingress instead of relying on our cloud provider to do so.

## Install

The cert-manager [install documentation](https://cert-manager.io/docs/installation/kubernetes/#steps)
states that its Custom Resource Definitions must be installed first outside of Helm before using the
official Helm chart. **Our installation script will take care of this automatically.**

Just run:

```shell
./prod/helm/tools/cert-manager/install_cert_mgr_remoting_prod.sh
```

## Upgrading

When upgrading this chart, do the following:

1. Update the `cert-manager` version number in [Chart.yaml](./Chart.yaml).

2. Download the Custom Resource Definitions for the new version from
  <https://github.com/jetstack/cert-manager/releases/download/v${VERSION}/cert-manager.crds.yaml> and vendor
  them in this directory as [cert-manager.crds.yaml](./cert-manager.crds.yaml). Our install script does not
  download the CRDs so that we are not reliant on having to access the cert-manager GitHub during installation.
