# Remote cache tools

## Remote cache usage reporter

The remote cache usage reporter runs as a job in k8s (every hour) it and calculates stats about cache usage on a per customer basis.
It does the following:

- pushes the data to Prometheus (via Push Gateway) - Visible in a [Grafana dashboard](https://grafana.toolchainlabs.com/d/NMgLF1TGz/remote-cache?orgId=1&refresh=1m) in the Redis Usage Per customer panel.
- Once a day it publishes this information to the #Remoting slack channel.
