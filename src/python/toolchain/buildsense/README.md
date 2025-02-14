# Build Stats Service

## Ingestion Setup for Kubernetes Dev cluster

* Set up dev [Kubernetes for your namespace](../../../../src/sh/db/README.md).
* Make sure you deploy a postgres DB instance into your dev namespace by running [src/sh/db/dev_db_setup.sh](../../../sh/db/dev_db_setup.sh)
* Install InfluxDB into your namespace: [prod/helm/tools/install_influxdb_buildsense_dev.sh](../../../../prod/helm/tools/install_influxdb_buildsense_dev.sh)
* Make sure required [secrets are properly setup in yourn namespace](../service/README.md#secrets-in-dev)
* Build & deploy proxy and related services:

```shell
./prod/helm/install_dev.sh users/ui users/api servicerouter  buildsense 
```

* Set up port forwarding for service router (and keep it running):

```shell
  ./src/sh/kubernetes/port_forward.sh servicerouter
```

* Create an auth token for buildsense (and possibly remote cache):

```shell
PANTS_CONFIG_FILES=pants.localdev.toml ./pants auth-acquire
```

## Accessing build data in OpenSearch dashboard (dev only)

We have a common OpenSearch (previously known as Elasticsearch) domain in dev (es-dev) which we use for both logging (of pods running on the dev cluster) and for buildsense in dev.
To access, you must be [connected to the VPN](../../../../prod/VPN.md) and use GSuite auth to authenticate.
The console is at <https://dev-es.toolchainlabs.com/_dashboards/app/home#/>

## Accessing pants work units metrics data

Pants work units metrics data is ingested into a [InfluxDB](https://www.influxdata.com/products/influxdb/) running on our Kubernetes cluster (in dev and in prod). This is done automatically by the buildsense worker (PantsMetricsIndexer)

### Loading data

Loading data is done by running a Django command from the buildsense/worker pod:

```shell
./manage.py index_pants_metrics
```

This command will iterate over builds and upload pants metrics data into the DB.

### Accessing data

In order to access data you need to connect to the production cluster and port forward the InfluxDB service to your local machine.

```shell
kubectl port-forward --context=prod-e1-1 --namespace=prod svc/influxdb 8086:80
```

Then the InfluxDB Web UI is accessible via [localhost](http://localhost:8086/)
The DB admin credentials are stored in a Kubernetes secret.
You can view the credentials required to access the web UI by running:

```shell
 kubectl get secret influxdb-master-creds  --context=prod-e1-1 --namespace=prod  -o json | jq -r ".data.secret_string" | base64 --decode | jq
```

## Customer Data Retention

We have the ability to delete old data for customers.
This is implemented by configuting a data retention policy for a given repository.
The data retention specifies for how long buildsense data should be retained.

Data retantion (deletion) is implemented by leveraging the Workflow system.
The `ProcessBuildDataRetention` is a per-repo object that sets the retention days.
This object is not automatically created for repos, making data retention indefinite.

The `ProcessBuildDataRetention` can be created for a given repo using a Django command from the buildsense api service.

```shell
./manage.py set_build_data_retention --repo=<customer-slug>/<repo-slug> --days=<retention days> --period=<retention check interval minutes>
```

By default, the workflow will run in dry run mode, which will only log the data marked for deletion and won't actually delete the data.
Switching dry run mode off can be done via toolshed (by modifying the relevant `ProcessBuildDataRetention` object) or by running the above command with the `--no-dry-run` option.

### How build deletion works

Build deletion is implemented in a [Workflow Worker](./ingestion/workers/retention.py).

1. The worker will use an query to OpenSearch (ES) to determine which builds needs to be deleted. There is a limit on how many builds will be deleted in any given run.
2. Load the RunInfo data for those builds from DynanmoDB.
3. Mark the Workflow objects associated with those builds as deleted
4. Delete builds from DynanmoDB - this will also trigger the Lambda function (via DynamoDB Streams) which will in turn delete the builds from OpenSearch
5. Delete the build data from S3.

