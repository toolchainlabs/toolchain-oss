# Kubernetes Alerts

## NodeHighNumberConntrackEntriesUsed

This alert fires when the connection tracking table used for firewall on a Kubernetes node is filling
up. The solution is to replace the node:

1. Find the `instance` attribute in the alert. This identifies the IP address of the node.
2. `kubectl --context=CLUSTER get nodes -o wide`. Find the node with the IP address matching the
  one from the alert. Note the name of the node (call it NODE_NAME in the following steps).
3. `kubectl --context=CLUSTER drain NODE_NAME --ignore-daemonsets --delete-emptydir-data`
4. Terminate instance in EC2 console (search for private dns name).
