# Production Logging

We use a combination of [Fluent Bit](https://fluentbit.io/), [OpenSearch](https://opensearch.org/) and [OpenSearch Dashboard](https://opensearch.org/docs/latest/dashboards/index/) to run our logging stack.

## Components

- Fluent Bit is the log collection software; it runs as a daemonset on our production cluster, and the pods run in the logging namespace.
- Elasticsearch - we use a AWS hosted Elasticsearch instance, which indexes all the logs collected by Fluent Bit.
- AWS ES Proxy - since AWS ES security model requires HTTP requests to it to be signed, and Fluent Bit currently doesn't have the ability to sign those requests, we use a proxy that sits between Fluent Bit and AWS ES in order to sign those requests.
- Logs Curator - this is a cron job that will regularly purge old logs. The way that ES works is a new index (similar to a table in the relational world) is created for each day of logs. The logs simply delete indexes that are older than X days.
- Kibana w/ AWS Cognito - we use Kibana as the web UI. It is protected using AWS Cognito which provides the authentication layer to Kibana.

## Accessing Logs

In order to access [OpenSearch Dashboard from the browser](https://logging.toolchainlabs.com/_dashboards),  you will need to be connected to the [Toolchain VPN](../../../VPN.md).

## Updating & Installing the logging chart

We have scripts to install and update the logging chart in kubernetes clusters:

- [prod-e1-1](./install_prod.sh) - prod/webapp cluster
- [remoting-prod-e1-1](./install_remoting_prod.sh) - remoting cluster
- [dev-e1-1](./install_dev.sh) - remoting cluster

## Searching & filtering logs - in production

There are two log index patterns, one for each cluster, this is visible on the left side if the UI in just below the search text bar on.

- prod-logs - logs from the prod-e1-1 cluster.
- remoting-prod-logs - logs from the remoting-prod-e1-1 cluster

Make sure you select the correct one in the `CHANGE INDEX PATTERN`

You should narrow down search by using metadata that is associated with each log entry.
The most common/useful way is to select a kubernetes namespace `kubernetes.namespace_name` and then filter using kubernetes labels associated with pod metadata: this will be named `kubernetes.labels.XXX` where XXX is the label name.
For example: `kubernetes.labels.app` for the `app` label and `kubernetes.labels.toolchain_product` for the `toolchain_product`label.

You can further narrow down by container name: `kubernetes.container_name`, this is mostly useful for our api services where we run multiple containers (nginx, gunicorn) in the same pod.

Toolchain python code runs under `gunicorn` container for api services and `worker` for workflow containers.

### Saved searches

There are a bunch of predefined filters that are saved in Kibana/ES that can serve both as a good starting point and as an easy way to access common used searches/filters.
Those are available from the Kibana/ES home page (in the sidebar, there will be a 'recently viewed' section), or by going to the [discover page](<https://logging.toolchainlabs.com/> _dashboards/app/discover#/) and accessing the saved searches by clicking the "Open" item in the menu bar (top right part of the page).

## Information in Logs

### Python logs

Log messages from our python code will contain code pointer (file name and line number) those can be useful when tracking down log messages back to the code.
for example, the code that generated the following log message can be found at `toolchain/workflow/work_executor.py` line: 287.

```logs
[2021-08-23 21:06:17 INFO WorkerThread-1 toolchain/workflow/work_executor.py:287] [buildsense-worker-85fd9c4df4-kchw7/1] Executed `_execute()` in 0.648s for workunit #744725 (IndexPantsMetrics(run_id=pants_run_2021_08_23_14_05_33_113_a341dfe038cf458f921ceb087587b8bf customer_id=exBgciGKk7hyzGVQ7MDsTn repo_id=E7YBxGBq7Eu7afkhpibY4f user_api_id=45ybqkXUcnJfaWaZARmAmK)) 
```

### gunicorn logs

For API & Web UI services we will also log the request id which is passed between devices as one service calls another.

For example, the request ID for this log message (from the buildsense-api pod) is `a33e1e18ce9500f7a53b503d9ce22263`.

```logs
[2021-08-23 21:08:31 INFO 17367 toolchain/buildsense/ingestion/run_info_raw_store.py:268 request_id=a33e1e18ce9500f7a53b503d9ce22263] save_build_file name='pants_run_log.txt' content_type='text/plain' size=571 key='prod/v1/buildsense/exBgciGKk7hyzGVQ7MDsTn/E7YBxGBq7Eu7afkhpibY4f/45ybqkXUcnJfaWaZARmAmK/pants_run_2021_08_23_14_08_22_392_7ea4ed127b114d379c08bad3df5b96d5/pants_run_log.txt' final_metadata={'compression': 'zlib'} dry_run=False
```

Searching for the request ID (without any other filters) will show logs messages from all the pods and code that processed the request.
So in this case there will be log message from both gunicorn and nginx in service router and nginx and gunicorn in buildsense-api

We also add the username & api id the the generic gunicorn request message (which also has the request ID).
For example, by searching for the same request id mentioned earlier we see:

```logs
127.0.0.1 - - [23/Aug/2021:21:08:31 +0000] a33e1e18ce9500f7a53b503d9ce22263 stuhood/45ybqkXUcnJfaWaZARmAmK "POST /api/v1/repos/pants/buildsense/pants_run_2021_08_23_14_08_22_392_7ea4ed127b114d379c08bad3df5b96d5/artifacts/" 201 4 "-" "pants/v2.7.0.dev4 toolchain/v0.13.
```

so it is easy to know which user made the request, in this case `stuhood/45ybqkXUcnJfaWaZARmAmK` what is the user agent (`pants/v2.7.0.dev4 toolchain/v0.13`), uri, method and HTTP status code and response size (4 bytes).

Since we log the username & api id it is easy to filter to see all the endpoints a given user hit over a defined period of time.
This be used to track down issues that a specific user/customer is having

### nginx logs

We [configure nginx logging to use structured logging (json)](../../../docker/django/nginx/nginx-edge.conf) this means that when using Kibana/ES we can easily filter by uri, user agent, status (http status code), user (remote user, available in downstream services), etc.
Those fields show up as `logJson.XXX` in Kibana/ES so for example: `logJson.status`, `logJson.remote_user`, etc...
