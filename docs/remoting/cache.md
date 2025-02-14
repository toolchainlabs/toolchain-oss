# Remote Cache Production

## Services

Remote cache services:

- `proxy_server`: Acts as frontend receiving requests from load balancer, authenticates user, and dispatches the
  request to backend services.
- `storage_server`: Backend service providing implementation of the CAS and Action Cache

Public endpoints:

- `cache.toolchain.com:443` - Production entry point to remote cache
- `staging.cache.toolchain.com:443` - Staging entry point to remote cache

## Deploys

The remote cache services use the same deploy tooling as other Toolchain services. See the
[deploy tooling docs](../../prod/helm/README.md) for more information.

Example:

0. Make an edit to code (or config).
    * If you have also edited the config map or values file, ensure that you bump the chart version.
1. Install to a dev environment: `./prod/helm/install_dev.sh storage-server` ... and validate the change.
2. Land your tested changes on `master`.
3. Build and deploy storage-server to staging: `./prod/helm/build_and_install_prod.sh storage-server`
4. Test the staging instance by setting `--toolchain-setup-base-url=https://staging.app.toolchain.com` in
   a Pants client.
5. Commit the resulting change and open a PR.
6. After the docker image change has landed on `master`, deploy to prod: `./prod/helm/install_prod.sh storage-server`

### Kubernetes cheatsheet

Read the [general `kubectl` cheatsheat](https://kubernetes.io/docs/reference/kubectl/cheatsheet/).

Some useful commands:

- Setting up `kubectl` context to access remoting-prod-e1-1:
  - Ensure that you are [authorized to access the cluster](../../prod/kubernetes/README.md#setting-up-kubernetes-cli-cluster-context).
  - Create the context by running: `./prod/kubernetes/kubectl_setup.sh remoting-prod-e1-1`
  - Make it the default context by running: `kubectl config use-context remoting-prod-e1-1`
  - Delete a context: `kubectl config delete-context remoting-prod-e1-1`
- List all running pods: `kubectl --context=remoting-prod-e1-1 -n prod get pods`
- Show details of a single pod: `kubectl --context=remoting-prod-e1-1 -n prod describe pod POD`
- Kill a pod: `kubectl --context=remoting-prod-e1-1 -n prod delete pod POD`
- List deployments: `kubectl --context=remoting-prod-e1-1 -n prod get deployments`
- Restart all pods in a deployment: `kubectl --context=remoting-prod-e1-1 -n prod rollout restart deployment/remoting-proxy-server`
- Scale a deployment to N pods: `kubectl --context=remoting-prod-e1-1 -n prod scale --replicas=N deployment/remoting-proxy-server`

## On-call

1. Monitoring #devops and #remoting Slack channels for alerts.
2. Monitor customer channels on Toolchain Slack for issues they raise.

## Alerts

All alerts currently email to ops-notify list, and some will be listed in Slack channels (#devops and #remoting).
None are triggering PagerDuty (yet!).

Alerts:

- `GrpcInFlightRequests` - A service tier may have become overloaded such that it may not recover.
  - We have seen a periodic issue (particularly with the `proxy_server`) such that once in-flight
    requests have gone high, they won't recover until the proxy tier is restarted.
- `CPUThrottlingHigh` - A container is being CPU throttled
  - Seen with `storage_server` due to bug with parsing Redis wire protocol. Upstream apparently fixed (which we updated
    to). Take a stacktrace if "new" then kill the pod to force a new pod to be created.
- `KubePodCrashLooping` - A container is being continually restarted
  - If happens too often, pods could end up in CrashLoopBackoff state. If so, kill the pods to clean the state and
    force them to be recreated.
- `GrpcErrorRate` - Triggers when too many gRPC errors in time period
  - for `Unauthenticated` error: Likely a new customer, but investigate if seen "too much"
  - for `Aborted` error: Ignore for now, likely caused by Pants cancelling connection.
  - other errors: Investigate since could be Pants client bug (e.g., if `InvalidArgument` error).

## Grafana Dashboards

- [Remote cache operational dashboard](https://grafana.toolchainlabs.com/d/NMgLF1TGz/remote-cache?orgId=1&refresh=1m)
- [Remote cache client metrics](https://grafana.toolchainlabs.com/d/nbzAnI6Mz/remote-cache-client-metrics?orgId=1&refresh=15m)
- [Storage analysis dashboard](https://grafana.toolchainlabs.com/d/mVm6YT9Gk/storage-analysis?orgId=1)
- [Kubernetes resource usage (by workload)](https://grafana.toolchainlabs.com/d/a164a7f0339f99e89cea5cb47e9be617/kubernetes-compute-resources-workload?orgId=1&refresh=10s&var-datasource=remoting&var-cluster=&var-namespace=prod&var-workload=remoting-proxy-server&var-type=deployment)

## Other runbooks

- [Redis runbook](./redis-prod.md)

## Procedures

### Cleanup EFS usage

Use the following procedure to cleanup EFS usage:

1. Find a storage-server pod to use for the shell. Run `kubectl --context=remoting-prod-e1-1 get pods -n prod -l app=remoting-storage-server`
  and then pick one. Call that pod POD_NAME in the following steps.
2. `kubectl --context=remoting-prod-e1-1 -n prod exec $POD_NAME -t -i -- /bin/bash
3. cd /data/cas/v1/instances
4. Expire entries older than 30 days: `find . -type f -name '*.bin' -atime +30 -delete`
