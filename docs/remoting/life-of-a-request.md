# Life of a Remote Execution Request

## Overview

This document covers the life of a remote execution request from when it leaves the REAPI client (e.g.,
Pants or [smoketest](https://github.com/toolchainlabs/remote-api-tools/tree/main/cmd/smoketest) through to its
execution on a Buildbox worker container running within customer infrastructure.

Assumptions:
- This is an "as currently built" design overview. Current as of 11/2/2022.
- Does not cover future changes including, for example, on-premises CAS.

## Request Flow

### REAPI client (e.g., Pants or smoketest)

1. The REAPI client generates [`Action`](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L394-L452)
and [`Command`](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L461-L600)
protobufs plus an "input root" consisting of a tree of `Directory` protobufs referencing files. These protobufs
collectively represent the process to execute in its entirety.
2. The protobufs and input root are uploaded to the CAS (or verified by the particular client to already
be present such as by using the CAS FindMissingBlobs operation). The controller will download the `Action` or `Command`
from the CAS if it needs to read any data out of them. (The execution request only contains digests for the `Action`
and `Command`.)
3. Client sends request via the [`Execute` operation on gRPC `Execution` service](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L113-L115)
to the cluster's gRPC endpoint. (For edge, the endpoint is `edge.toolchain.com`. For dev-e1-1 development, this will
usually be `localhost:8980` from forwarding the gRPC endpoint using `kubectl port-forward`.)
  - The gRPC `authorization` header will be set with a JWT authenticating the client to Toolchain's systems.
  The format of the JWT is beyond the scope of this document.
  - This is a server-streaming gRPC operation. The cluster will send a stream of [`Operation` protobufs messages](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/googleapis/google/longrunning/operations.proto#L126-L162)
  in which the `response` field will be an [`ExecuteResposne` protobuf messages](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L1243-L1274)
  updating the client on the current status of the execution request.

Other gRPC operations:
- If the client is disconnected from the cluster, it can use the [`WaitExecution` operation on the gRPC `Execution`
service](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/bazelbuild_remote-apis/build/bazel/remote/execution/v2/remote_execution.proto#L123)
to reconnect to the stream of `ExecuteResponse` messages for the execution request.
- Status of an execution request is also available via the [Operation gRPC service](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/googleapis/google/longrunning/operations.proto#L54-L124)
which is a "well known" Google-provided API for servers with long-running operations. 

### AWS Load Balancer

The cluster's gRPC endpoint is fronted by an AWS Application Load Balancer in gRPC mode. The load balancer
performs TLS termination such that the request will be unencrypted within Toolchain's cloud.

The `Execute` gRPC request is routed to an instance of aws-load-balancer-controller running in the
`remoting-prod-e1-1` Kubernetes cluster.

aws-load-balancer-controller then uses an `Ingress` resource to find which Service (and then pod) to receive the 
execution request. An instance of `proxy-server` will be chosen.

### proxy-server

`proxy-server` is the first Toolchain-specific code to receive REAPI gRPC requests. It authenticates and then
dispatches REAPI requests to downstream backend services for further processing. (The current backend 
services are `storage-server` for CAS and Action Cache and the `execution-server` for remote execution.)

1. The execution request enters proxy-server and is routed to
[`ExecutionService`](https://github.com/toolchainlabs/toolchain/blob/043f81de15c90a1fb1c91883aacdfdd557b4e451/src/rust/proxy/src/server/execution_service.rs#L28)
for processing.
2. The request's `authorization` header is checked to ensure it is validly-signed and contains the `exec` scope.
See [`get_client` method](https://github.com/toolchainlabs/toolchain/blob/043f81de15c90a1fb1c91883aacdfdd557b4e451/src/rust/proxy/src/server/execution_service.rs#L35).  
The `get_client` method also selects a particular backend to use for the request based on the REAPI instance name.
  * The `execute` function then dispatches the execution request to the Tonic library for sending to the backend. 
3. The `ginepro` crate's `LoadBalancedChannel` struct provides an in-process load balancer to load balance across
multiple gRPC backends.
  * The backends are discovered via in-cluster Kubernetes DNS endpoint for the associated `Service` resource.
    That `Service` is in "headless" mode which means that the IPs of the downstream pods are exposed in the DNS
    response instead of the IP of a `kube-proxy` instance. Thus, `LoadBalancedChannel` is able to contact the
    backend pods directly.

### execution-server

1. The execution request is received by the execution-server. The request is put in a single global queue (see
   https://github.com/toolchainlabs/toolchain/issues/16850 about partitioning that queue by properties).
2. The Buildbox worker will contact the execution-server using the [Bots protocol][] and pull work from the
   queue. This is known as taking a "lease" for the work.
3. If the request is completed before it is canceled by the caller, the worker will complete the lease and the
   finish the work, which makes the result available to the `Execute` and `WaitExecution` methods.

### Buildbox

### Overview

The worker and runner come from the ["buildbox" subproject of BuildGrid](https://gitlab.com/BuildGrid/buildbox).
The components use the Google "Remote Workers API" (aka [Bots protocol][]) to communicate with the execution-server.

#### Components

The Buildbox worker process consists of several components:

- buildbox-worker ("worker")
  - The worker process makes an RPC call to the execution-server to "pull" the next execution request to execute.
    That RPC call is forwarded through `proxy-server`.
- buildbox-casd ("casd")
  - A "local CAS" proxy which is responsible for caching CAS accesses and also staging input roots for the 
    runner by mounting them as FUSE mounts.
- buildbox-run-hosttools ("runner")
  - The "runner" invoked by `buildbox-worker` to actually execute the execution request. This runner just runs
    the request in the container without providing any other measure of isolation.

#### Request Flow

1. Worker receives the execution request via a RPC call to the controller.
2. Worker invokes the runner [with a standard set of CLI flags](https://gitlab.com/BuildGrid/buildbox/buildbox-worker/-/blob/master/buildboxworker/buildboxworker_runnercommandutils.cpp)
defined for buildbox. (Also see [the standard runner help message](https://gitlab.com/BuildGrid/buildbox/buildbox-common/-/blob/master/buildbox-common/buildboxcommon/buildboxcommon_runner.cpp)
in buildboxcommon.)
  - Options include file paths for where runner should redirect stdout and stderr, where the `Action` to execute is,
  and where to write the final `ActionResult` protobuf message for the execution request.
3. Runner is invoked and performs several steps:
  1. Stage the input root using the [`LocalContentAddressableStorage` gRPC service](https://gitlab.com/BuildGrid/buildbox/buildbox-common/-/blob/master/protos/build/buildgrid/local_cas.proto) provided by `casd`:
    1. Runner makes `StageTree` RPC call to `casd`. Handled by [`LocalCasStagedDirectory` in buildboxcommon](https://gitlab.com/BuildGrid/buildbox/buildbox-common/-/blob/master/buildbox-common/buildboxcommon/buildboxcommon_localcasstageddirectory.cpp).
    2. casd: Receives request and mounts a FUSE filesystem.
      - TODO: Add details on how FUSE is setup to provide a "CAS" filesystem
    3. The RPC call is a client-streaming RPC call. So long as the stream remains open, the input root will exist.
     Once the stream closes, then casd will remove the input root mount.
  2. Invoke the subprocess to actually execute the execution request.
  3. Capture outputs and stdout/stderr.
    1. Runner `CaptureTree` and `CaptureFiles` RPCs to casd to capture output directories and output files,
       respectively, into the CAS.
    2. Stdout and stderr are written to files specified by worker and captured as well to CAS by casd.
       Runner arranges for casd to capture stdout/stderr unless worker passed `--no-logs-capture` flag to runner.
  4. Runner writes `ActionResult` to a file path specified by the `worker`.
5. Worker reads the `ActionResult` from the file and makes call to controller to provide the `ActionResult`.
  - TODO: Add details from Remote Workers API for providing `ActionResult` to controller. 
6. Controller returns `ActionResult` to the ultimate client which then passes through proxy-server and other
components on its way back to the ultimate client.

TODO: Research and verify this flow.

[Bots protocol]: https://github.com/toolchainlabs/toolchain/blob/dc2711b62095f13efcc663ff04280aaddcc63136/src/rust/protos/protos/googleapis/google/devtools/remoteworkers/v1test2/bots.proto#L64
