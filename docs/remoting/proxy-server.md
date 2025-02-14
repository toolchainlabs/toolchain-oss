# Proxy Server

`proxy-server` is an application-level proxy for several Remote Execution API ("REAPI") services including:
- [`ContentAddressableStorage`](https://github.com/toolchainlabs/toolchain/blob/a1d88e75b99ecd96eedfe18b7b0010447097b6d6/src/go/src/toolchain/remoting/protos/build/bazel/remote/execution/v2/remote_execution.proto#L251)
  - Read and write blobs in the CAS. See `ByteStream` service for streaming API for reading and writing blobs.
- [`ActionCache`](https://github.com/toolchainlabs/toolchain/blob/a1d88e75b99ecd96eedfe18b7b0010447097b6d6/src/go/src/toolchain/remoting/protos/build/bazel/remote/execution/v2/remote_execution.proto#L138)
  - Maps digests of `Action` protos to `ActionResult` protos.
- [`Execution`](https://github.com/toolchainlabs/toolchain/blob/a1d88e75b99ecd96eedfe18b7b0010447097b6d6/src/go/src/toolchain/remoting/protos/build/bazel/remote/execution/v2/remote_execution.proto#L43)
  - Submit and wait for result of remote execution requests.
- [`Capabilities`](https://github.com/toolchainlabs/toolchain/blob/a1d88e75b99ecd96eedfe18b7b0010447097b6d6/src/go/src/toolchain/remoting/protos/build/bazel/remote/execution/v2/remote_execution.proto#L351)
  - Return metadata about a CAS and remote execution system.
- [`Operations`](https://github.com/toolchainlabs/toolchain/blob/a1d88e75b99ecd96eedfe18b7b0010447097b6d6/src/go/src/toolchain/remoting/protos/google/longrunning/operations.proto)
  - Access metadata about running remote execution operations.
- [`ByteStream`](https://github.com/toolchainlabs/toolchain/blob/60f48e0759a269fcf02996b46dc356d4b8a8de90/src/rust/protos/protos/googleapis/google/bytestream/bytestream.proto#L49)
  - Streaming API for reading and writing blobs.

Toolchain uses `proxy-server` to enforce a user's authorization to use the remote cache and remote execution system.
This is done with a JWT token signed by Buildsense with one or more of the JWT scopes:
- `cache_ro`: Read-only access to the CAS and Action Cache
- `cache_rw`: Read-write access to the CAS and Action Cache
- `exec`: Access to remote execution

## Configuration Guide

The configuration file is a YAML-format which configures REAPI backends to be proxied by `proxy-server`.

The configuration file is read using a series of `struct`s defined in Rust. See the relevant
[config.rs](https://github.com/toolchainlabs/toolchain/blob/26660a0506b0a9af258b296632c95a7f22bfb4e7/src/rust/proxy_server/src/config.rs)
for the definitive resource on what the configuration file accepts.

### Top-level keys

| Tag | Required | Purpose|
|----|---------|-----------------------------------------------------------------------------------------------|
|backends|Yes| Define names for REAPI endpoints to be used in other parts of the configuration.|
|backend_timeouts|No| Configure timeouts to use when forwarding requests to backends.|
|default_backends|Yes| Define the default backend(s) to receive various REAPI services.|
|grpc|No| gRPC-specific configuration|
|infra|No| Configuration for admin endpoints.|
|jwk_set_path|Yes| File path containing a JWK Set with the authentication key to use when validating JWT tokens for auth.|
|auth_token_mapping_path|Yes| File path to JSON file mapping tokens to their auth metadata.|
|listen_addresses|Yes| Configuration for which addresses to listen to for which services.|
|per_instance_backends|No| Define specific backends to receive REAPI traffic sent under a specific REAPI instance name.|

#### `backends`

Define names for REAPI endpoints to be used in other parts of the configuration. This allows host/port to be specified
once and then reused.

```yaml
backends:
  xyzzy:
    address: some.svc.ns.cluster.local:8980
    connections: 2
  another:
    address: another.svc.ns.cluster.local:8980
    connections: 1
```

#### `default_backends`

Define the default backend(s) to receive various REAPI services:

- `cas`: Backend for `ContentAddressableStorage` and `ByteStream` services.
- `action_cache`: Backend for `ActionCache` service.
- `execution`: (optional) Backend for `Execution` and `Operations` services. If not specified, then proxy-server
will return an error that remote execution requests are not supported.

These can overridden by `per_instance_backends` top-level key based on REAPI instance name (including `execution`
if not specified here).

```yaml
default_backends:
  cas: xyzzy
  action_cache: xyzzy
  execution: another
```

#### `per_instance_backends`

Define specific backends to receive REAPI traffic sent under a specific REAPI instance name. Configuration is a map
of REAPI instance names to a dictionary containing `cas`, `action_cache`, and `execution` entries with same meaning
as for the `default_backends` top-level key.

```yaml
per_instance_backends:
  foo:
    cas: xyzzy
    action_cache: xyzzy
  bar:
    cas: xyzzy
    action_cache: xyzzy
    execution: another
```

#### `backend_timeouts`

```yaml
backend_timeouts:
  get_action_result: 1000  # Time in milliseconds to wait before giving up on forwarding GetActionResult RPCs.
```

#### `listen_addresses`

A list of configuration for each address that the binary should listen to for incoming connections. Each entry must set:

- `addr` to the `HOST:PORT`, e.g. `0.0.0.0:8980`
- `auth_scheme` to either `jwt` or `auth_token`
- `allowed_service_names` to the services that are recognized on the port. The names come from the `SERVICE_NAME` values in the Rust code, e.g. `build.bazel.remote.execution.v2.ActionCache`. This should be set to the minimum required.

The binary will create a server for each listen_address. However, this is not intended to be a scheme for increased concurrency. It's meant to instead allow us to define different interfaces, specifically a workers server that uses an auth token vs. our normal remote cache server that uses JWT.

The output configuration (e.g. `backends`)  and infrastucture configuration are shared amongst all listen_addresses.
