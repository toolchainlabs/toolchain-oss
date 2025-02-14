# Execution

Remote execution occurs via the `execution-server`, to which `buildbox` workers and remote execution clients connect.

## Deployment

### `execution-server`

The `execution-server` uses the same deploy tooling as other Toolchain services. See the
[deploy tooling docs](../../prod/helm/README.md) for more information.

## Alerts

All alerts currently email to ops-notify list, and some will be listed in Slack channels (#devops and #remoting).

Alerts:

- `WorkersConnected` - Indicates that not enough ECS workers are connected to a particular `execution-server` instance.
  - The impact of this alert is that jobs attempting to execute via remote execution will hang.
  - Check the ECS console or Cloud Watch logs in AWS to see how/why the workers exited. Use the `Buildbox Workers`
    instructions above to redeploy them if necessary.
