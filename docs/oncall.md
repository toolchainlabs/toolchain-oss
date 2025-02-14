# On call at Toolchain

## Relevant docs

- [General runbook](./RUNBOOK.md)
- [Logging](./../prod/helm/observability/logging/README.md)
- [Monitoring](./../prod/helm/observability/monitoring/README.md)
- Services Docs:
  - [Service Router](./../src/python/toolchain/servicerouter/README.md)
  - [Buildsense](./../src/python/toolchain/buildsense/README.md)
  - [Toolshed](./../src/python/toolchain/toolshed/README.md)
  - [Users & Auth](./../src/python/toolchain/users/README.md)
- Common software (used by multiple services):
  - [Workflow Runbook](./../src/python/toolchain/workflow/RUNBOOK.md)

## On call checklist

Before going on call:

- You can connect to the [VPN](./../prod/VPN.md)
- You can log on to the [AWS Console](https://console.aws.amazon.com/console/home?region=us-east-1#) and that your password is not about to expire or expired.
- Your local [AWS credentials](./../SETUP.md#aws-setup) are up to date (try running `aws s3api list-buckets` and make sure it works)
- You can connect to the [prod & remoting Kubernetes clusters](./../prod/kubernetes/README.md)
- You can access [production logs](./../prod/helm/observability/logging/README.md)
- You can logon to [toolshed in production](https://toolshed.toolchainlabs.com)
- You can logon to [Grafana](https://grafana.toolchainlabs.com/dashboards)
- Your PagerDuty & Duo apps are up to date on your phone.
- You have the the devops tools we use installed, specifically: terraform, helm, kubectl. [current versions](../src/sh/setup/ensure_util_versions.sh#L169-L180)
