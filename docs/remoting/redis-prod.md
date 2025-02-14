# Redis Production Playbook

## Access Redis Directly

1. Ensure that `remoting-prod-e1-1` is in your kubectl configuration:
   `./prod/kubernetes/kubectl_setup.sh remoting-prod-e1-1`

2. Run a shell in Kubernetes:
   `kubectl --context=remoting-prod-e1-1 -n prod run shell --image=283194185447.dkr.ecr.us-east-1.amazonaws.com/tools/redis-cli:latest -t -i`

3. Run Redis CLI: `redis-cli -h remoting-storage-2-rg-1.trn9gg.ng.0001.use1.cache.amazonaws.com`

   Note: The hostname of the production Redis instance can be found by running
   `terraform output` in `prod/terraform/resources/us-east-1/remoting/remoting-prod-e1-1`.

## Procedures

### Wipe the cache

1. Follow the instructions above to run the Redis CLI.

2. Run the `FLUSHDB ASYNC` command to wipe the entire cache.

### Dump Redis key names and sizes to a file

1. Follow steps 1-2 in the instructions for running the Redis CLI to access a shell on the cluster.

2. In another terminal (on a Linux host), build the `dump_redis_metadata.py` PEX:
   `./pants package src/python/toolchain/remoting:dump_redis_metadata`

3. Copy the PEX file to the shell pod:
   `kubectl --context=remoting-prod-e1-1 -n prod cp dist/src.python.toolchain.remoting/dump_redis_metadata.pex shell:/tmp/dump_redis_metadata.pex`

4. In the shell running on the cluster, dump the Redis keys using the read-only Elasticache endpoint:
   `/tmp/dump_redis_metadata.pex --redis-host=remoting-storage-2-rg-1-ro.trn9gg.ng.0001.use1.cache.amazonaws.com --output=redis-key-sizes.csv`

5. Copy the CSV file back to your machine:
   `kubectl --context=remoting-prod-e1-1 -n prod cp shell:redis-key-sizes.csv redis-key-sizes.csv`
