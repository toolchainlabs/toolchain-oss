# Storage Server

`storage-server` implements the CAS and Action Cache APIs of the REAPI.

## Configuration Guide

The configuration file is a YAML-format which configures the CAS and Action Cache components of `storage-server`.

The configuration file is read using a series of `struct`s defined in Rust. See the relevant
[config.rs](https://github.com/toolchainlabs/toolchain/blob/45023704476505db1db0062be78f845cb157947f/src/rust/storage_server/src/config.rs)
for the definitive resource on what the configuration file accepts.

### Top-level keys

|Tag| Required |Purpose|
|---|----------|-------|
|action_cache|Yes|Storage stack for Action Cache operations. See storage stack config for acceptable configuration under this key.|
|cas|Yes|Storage stack for CAS operations. See storage stack config for acceptable configuration under this key.|
|check_action_cache_completeness|No|If true, then check completness of the Action Cache when client calls `GetActionResult` RPC.|
|completeness_check_probability|No|Integer 0-1000 representing probabability of checking completeness of Action Cache entries.|
|grpc|No|gRPC-specific configuration|
|infra|No|Configuration for admin endpoints.|
|listen_address| Yes      |Host/port where to listen for incoming requests. For example, `0.0.0.0:8980` would listen on port 8980 on all interfaces.|
|redis_backends|No|Names and endpoints for Redis backends which are then referenced by name in a storage stack config. Only required if a Redis storage driver is used.|
|amberflo_backend|No|Amberflo metering configuration. Only required if `metered` storage driver in use.|

#### `redis_backends`

Defines Redis server instances that can be used by storage stacks.

```yaml
redis_backends:
  NAME:
    address: ENDPOINT_IP_PORT  # Host/port for primary (read/write) endpoint.
    read_only_address: ENDPOINT_IP_PORT  # Optional. Host/port endpoint for reads
    num_connections: N  # Number of connections to open to this backend
    use_primary_for_read_only_probability: N  # Optional.
```

|Key| Required | Purpose                                                                                                                |
|---|----------|------------------------------------------------------------------------------------------------------------------------|
|address| Yes      | Host/port for the Redis server's primary (read/write) endpoint.                                                        |
|read_only_address| No       | Host/port of a Redis endpoint to which read-only traffic will be sent.                                                 |
|num_connections| No       | Number of connections to open to this backend. Defaults to 20.                                                         |
|use_primary_for_read_only_probability|No| Integer probability between 0-1000 for when to send read traffic to primary. Only relevant if `read_only_address` set. |

#### `amberflo_backend`

Configures how Amberflo metering events are generated and where they are sent to.

|Key|Required|Purpose|
|---|--------|-------|
|customer_id_prefix|Yes|String to prefix to customer IDs when generating customer ID for Amberflo events.|
|api_key_file|Yes|File path to a JSON file with the API key to use for Amberflo API calls. API key should be in `api_key` JSON key.|
|aggregation_window_duration_secs|Yes|Aggregation window size in seconds. Events are aggregated over this window and then sent as one event per customer.|
|env_dimension|Yes|Value to set for the `env` extra event dimension. Allows distinguishing prod/staging/edge in events.|
|api_ingest_url|No|Amberflo API endpoint. Defaults to the main API endpoint if not specified.| 

### Storage Drivers

The following configuration snippets appear under the `cas` and `action_cache` top-level keys to configure
"storage stacks" which define how storage requests are resolved.

#### Local driver

Stores blobs in the local filesystem. Specify `base_path` to control where the blobs are stored. 

```yaml
local:
  base_path: PATH
```

#### Size split driver

Switches between two different underlying storage drivers depending on whether the size of the blob is less than
or equal to the given value.

```yaml
size_split:
  size: SIZE
  smaller:
    # Storage driver config where "smaller" blobs will be accessed.
  larger:
    # Storage driver config where "larger" blobs will be accessed.
```

#### Redis driver

Stores blobs directly in Redis. The top-level `redis_backends` key must be defined with one or more Redis servers
to reference by name in this configuration.

```yaml
redis_direct:
  backend: BACKEND_NAME
  prefix: PREFIX
```

`BACKEND_NAME` is the name of a Redis backend as defined by the top-level `redis_backends` key.

`PREFIX` is a string to prefix to all Redis keys stored by this storage driver. This is useful for being able to write
CAS and Action Cache entries to the same Redis server without interference.

#### Dark launch driver

The "dark launch" driver allows incrementally transitioning users between two different storage stacks when launching
a significant changes or new drivers into production. The choice of whether the use the "first" (old) or "second" (new)
storage stacks is made based on the REAPI instance name.

By default, the dark launch driver writes to both storage stacks (unless `write_to_secondary` is set to `false`) and
only reads from the primary storage stack.

```yaml
dark_launch:
  storage2_instance_names:
    - Instance1
    - SecondInstanceName
  storage1:
    # Storage driver config if the instance name IS NOT in `storage2_instance_names`.
    # This is the "old" storage stack.
  storage2:
    # Storage driver config if the instance name IS in `storage2_instance_names`.
    # This is the "new" storage stack.
  write_to_secondary: true  # Optional. Defaults to true. Controls whether the derive
```

#### Sharded driver

The sharded driver distributes requests among one or more underlying storage stacks for shards based on
consistent hashing of the blob's digest. This is application-level sharding. High availability is not required of
the underlying storage stacks, but rather is provided by writing blobs to multiple shards (as controlled by the
`num_replicas` key).

```yaml
sharded:
  num_replicas: 2 # Number of shards to write to including a blob's primary shard.
  shards:
    - shard_key: UNIQUE_SHARD_KEY
      storage:
        # Storage driver config for this shard.
    ...
```

`UNIQUE_SHARD_KEY` is a string used to define how the shard hashes into the consistent hash ring used to distribute
blobs. It must be unique among all of the shards and must be stable, i.e. once assigned it should not change for 
life of the particular shard. Changing the shard key is equivalent to removing the old shard and introducing a new
shard.

#### Read cache (fast/slow) driver

The read cache ("fast/slow") driver caches a slower storage stack using a (hopefully) faster storage stack.

```yaml
read_cache:
  fast:
    # Storage driver config for the "faster" storage stack. E.g., Redis.
  slow:
    # Storage driver config for the "slower" storage stack. E.g., EFS.
```

#### Amberflo metering driver

The Amberflo "metered" storage driver monitors storage usage and sends metering events to Amberflo as
specified under the top-level `amberflo_backend` key.

```yaml
metered:
  # Storage driver config to be metered to Amberflo.
```

#### Memory driver

Stores blobs in memory.

```yaml
memory: {}
```

Warning: The `memory` driver does not have a maximum storage limit and should not be used in production configuration.

### Obsolete / unused storage drivers

- Chunked Redis (split large blobs into Redis) `redis_chunked`
- Existence cache `existence_cache`
- Verify digests of values being read (`read_digest_verifier`)
  - Note: The digests of blobs being written is always verified.

