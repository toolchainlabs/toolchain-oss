# Requirements

- Access to the Remote Execution Alpha (contact us in Slack).
- An installation of Pants running `2.15.0` or greater.
- [Authenticated](doc:getting-started-with-toolchain) Toolchain Pants plugin `>=0.25.0`.
- Worker machines compatible with your CI environment:
  - Toolchain remote execution uses a "bring your own worker" model: worker machines run a `worker` process provided by Toolchain, and execute work on behalf of Pants clients.

# Setup

## Workers

Worker machines (running in Kubernetes, VMs, or directly on your hardware) run the Toolchain `worker` process, which connects to Toolchain and long-polls for work to do on on behalf of your Pants clients.

Rather than running "an entire build" on one machine (as a CI provider like Circle CI or Github Actions do), remote execution concurrently schedules the individual processes which make up a Pants build across all workers. The Toolchain remote execution scheduler will transparently reschedule processes if workers disappear, so you can safely use the cheapest possible machines as workers (AWS or GCP Spot instances, for example), and scale up and down dynamically without impacting your user experience.

### Deployment

A common deployment model for workers is to use a Kubernetes Deployment that defines a series of Pods. Each Pod runs a Docker image containing your CI dependencies, with the `worker` process as its entrypoint:

```shell
# Assuming a machine/Pod with 8 cores:
worker \
  --worker-concurrency=8 \
  --cache-directory=/var/worker-cache
```

In Kubernetes, it is also possible to define a HorizontalPodAutoscaler which will dynamically create more worker Pods when their CPU usage is high (allowing you to scale down to 1 Pod when your CI is idle). That might look like the following:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: remote-exec-autoscale
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: <DEPLPOYMENT-NAME>
  minReplicas: 1
  maxReplicas: 64
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
    scaleUp:
      stabilizationWindowSeconds: 30
  metrics:
   - type: Resource
     resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 40
```

### Requirements

In addition to any other requirements of your CI environment, the `worker` process requires the following packages to be installed:

- `libprotobuf23`
- `libgrpc++1`

On `ubuntu`, these can be installed with `apt-get install libprotobuf23 libgrpc++1`.

### Installation

The worker binary is hosted in S3: to fetch and verify the most recent version, use a command like:

```shell
worker_version="2023-02-10-d37dea39d0"
wworker_sha256="9f8e84ae092038c0edd4634345ae4365c48cbf4b7729b8ea447e382fefd5fb4c"

curl --fail -L -o worker "https://s3.amazonaws.com/binaries.us-east-1.toolchain.com/remote-workers/alpha/${worker_version}/remote-workers" && \
  echo "${worker_sha256}  worker" | sha256sum -c - && \
  mv worker /usr/local/bin/ && \
  chmod +x /usr/local/bin/worker
```

## Pants clients

1. Add an environment definition and recursive target default to enable running tests remotely when remote execution is enabled:

   1. In a `BUILD` file at the root of your repository, add:

   ```python BUILD
    # Apply the `remote` environment to all targets.
    __defaults__(all={"environment": "remote"})

    # A remote environment target which will fall back to a local environment when
    # remote execution is disabled.
    remote_environment(  
        name="remote",  
        fallback_environment="__local__",  
        python_bootstrap_search_path=["<PATH>"],  
    )
   ```

   2. In `pants.toml`, add:

   ```toml pants.toml
   [environments-preview.names]  
   remote = "//:remote"

   [auth-acquire]  
   remote_execution = true
   ```
2. Update your CI token to include the remote execution permission.
   1. Run `auth-acquire`:
   ```shell
   ./pants auth-acquire --auth-acquire-for-ci
   ```
   2. Replace your existing CI token with this new token – usually declared as a secret exposed in the `TOOLCHAIN_AUTH_TOKEN` environment.
3. Enable remote execution for your CI environment:

   1. In `pants.ci.toml`, enable remote execution, and choose the number of remote processes each Pants client will attempt to start concurrently (based on the number of workers that you have available):

   ```toml pants.ci.toml
   [GLOBAL]  
   remote_execution = true  
   remote_cache_read = true  
   remote_cache_write = true  
   remote_execution_append_only_caches_base_path = "/toolchain/caches"
   # The number of remote processes that each Pants client should  attempt to start.
   process_execution_remote_parallelism = 16
   ```

# Usage

Once remote execution is enabled in CI, it should be transparent that it is in use, except that when processes miss the cache, they will report that they ran remotely:

```text
✓ src/python/example/models_test.py:tests succeeded in 4.67s (ran remotely).  
✓ src/python/example/sitemap_test.py:tests succeeded in 10.35s (ran remotely).
```

## Debugging

To disable remote execution, set `remote_execution = false`. Remote caching will still be used.

```toml pants.ci.toml
[GLOBAL]  
remote_execution = false
```

Please let us know via a private Slack thread or DM when you are having issues or slowdowns with remote execution. We’re actively iterating to improve remote execution, and would appreciate any and all feedback!