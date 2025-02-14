# Monitoring & Alerting at Toolchain

We are using Prometheus, Alert Manager & Grafana to do that.

We leverage the [Prometheus Operator](https://github.com/coreos/prometheus-operator) and the [helm chart](https://github.com/helm/charts/tree/master/stable/prometheus-operator) associated with it to install & configure monitoring components into our Kubernetes cluster.

We use the following helm chart as sub-charts to our monitoring charts:

* [Prometheus Operator](https://github.com/coreos/prometheus-operator) - See detailed explanation below
* [Prometheus Cloudwatch Exporter](https://github.com/prometheus/cloudwatch_exporter) - This exporter calls the AWS API to read the metrics and makes them available in Prometheus
* [Prometheus Pushgateway](https://github.com/prometheus/pushgateway) - We use the push gateway to capture metrics from components that are either short lived (i.e. Kubernetes jobs) or from components/applications that otherwise don't expose a web server that prometheus can scrape (currently, our LevelDB Watcher container running in dependency-api pods)

On a high level, the Prometheus Operator helm chart does two things for us:

1. Define [Kubernetes Custom Resources](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/)

    * [PodMonitor](https://github.com/coreos/prometheus-operator/blob/master/Documentation/design.md#podmonitor) - monitors individual on or more pods. We define two [PodMonitor objects](https://github.com/coreos/prometheus-operator/blob/master/Documentation/api.md#podmonitor). One to monitor our services (pods who run nginx) and one to monitor workflow workers. A pod monitor selects the pods it monitors using [standard kubernetes labels & namespace selectors](https://kubernetes.io/docs/concepts/overview/working-with-objects/labels/). It uses a [namespaceSelector](https://github.com/coreos/prometheus-operator/blob/master/Documentation/api.md#namespaceselector) and a [label selector](https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.11/#labelselector-v1-meta)

    * [Prometheus](https://github.com/coreos/prometheus-operator/blob/ca400fdc3edd0af0df896a338eca270e115b74d7/Documentation/design.md#prometheus) - defines an instance of the [Prometheus](https://prometheus.io/docs/prometheus/latest/getting_started/) app/server. From a functionally perspective, it selects a bunch of ServiceMonitor resources, selecting them based on [labels](https://github.com/coreos/prometheus-operator/blob/ca400fdc3edd0af0df896a338eca270e115b74d7/Documentation/api.md#prometheusspec) and scrapes them to collect metrics & create alerts (based on associated PrometheusRule resources). It needs to point to one or more AlertManager custom resources

    * [AlertManager](https://github.com/coreos/prometheus-operator/blob/ca400fdc3edd0af0df896a338eca270e115b74d7/Documentation/design.md#alertmanager) - defines an instance of the [Alert Manager](https://prometheus.io/docs/alerting/alertmanager/) Service

    * [PrometheusRule](https://github.com/coreos/prometheus-operator/blob/ca400fdc3edd0af0df896a338eca270e115b74d7/Documentation/design.md#prometheusrule) - this resource defines either a [recording rule](https://prometheus.io/docs/prometheus/latest/configuration/recording_rules/) or an [alerting rule](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/).API is documented [here](https://github.com/coreos/prometheus-operator/blob/ca400fdc3edd0af0df896a338eca270e115b74d7/Documentation/api.md#prometheusrule)

2. Define a set of instances of those custom resources to monitor the Kubernetes cluster and its components (etcd, kubelets, nodes, etc...)

We build on top of that and define custom resources to monitor our apps & services.
We define the following service monitors:

* monitor-services - Hits the [/metricsz](../../../../src/python/toolchain/django/site/views/urls_base.py) endpoint on our django services api services
* monitor-workers - Hits the [metricsz](../../../../src/python/toolchain/workflow/urls_worker.py) endpoint on our worker pods to monitor out workflow services prods.

## Grafana Dashboards

Dashboards are provisioned as Kubernetes config maps and are located under [the dashboards folder](grafana/dashboards).

While we can use the Grafana web UI to create dashboards, we want to keep copies in the repo. To do this, create (or update) a dashboard in Grafana and export it as json. Then move the json file under the [dashboards](grafana/dashboards/) directory.

Make sure you bump the chart version otherwise the change won't get picked up by helm.

Do not update any of the "builtin" dashboard that we [sync](../../../../src/python/toolchain/prod/sync_grafana_dashboards.py) from [kube-prometheus](https://github.com/prometheus-operator/kube-prometheus/tree/main/manifests).
It is better to either try to get a change to those dashboards upstream or just create a new dashboard.

## How to access monitoring in production

* __Grafana__:

We have Grafana configured with Google Auth, so use your Toolchain google account to login at: <https://grafana.toolchainlabs.com/>
You will need to be connected to VPN in order to access it.

For other components, we run all of our monitoring components in their own namespace (named monitoring).
In order to access the various components, use the `kubectl` port forwarding command.
First examine the list of services in the monitoring namespace:

```shell
kubectl get services --namespace monitoring
```

Then use the port forward command on the desired service:

* __Prometheus__
  * List of scraped targets and their status at <http://localhost:9090/targets>
  * Alerts being generated and monitored by this Prometheus instances: <http://localhost:9090/alerts>
  * Querying metrics collected by the Prometheus instances: <http://localhost:9090/graph>

```shell
kubectl port-forward --namespace monitoring svc/prod-monitoring-prometheus-prometheus 9090:80
```

* __Alert Manager:__
  * Status & config: <http://localhost:9093/#/status>
  * Configure/Set [silences](https://prometheus.io/docs/alerting/alertmanager/#silences): <http://localhost:9093/#/silences>
  * Current alerts: <http://localhost:9093/#/alerts>

```shell
    kubectl port-forward --namespace monitoring svc/prod-monitoring-prometheus-alertmanager 9093:9093
```

## Deploying monitoring chart

The monitoring chart can be deployed to both remoting cluster and prod cluster.
There is a script for each luster:

* [Prod cluster script](install_prod.sh)
* [Remoting cluster script](install_remoting_prod.sh)

Use the the relevant script to package and deploy the monitoring chart/stack to the cluster. The script will fill in secrets from AWS Secrets Manager into the chart values.

```shell
./prod/helm/observability/monitoring/install_prod.sh
```

## Deploying Grafana

Use the `prod/helm/observability/monitoring/install_grafana.sh` script to package and deploy the grafana chart to the production cluster

```shell
./prod/helm/observability/monitoring/install_grafana.sh
```

## Updating credentials for prod-monitoring-email-user

Alert manager is configured with SMTP credentials in order to send out emails when alerts occur.
The monitoring installation script reads the IAM user credentials from `prod/monitoring` secrets in AWS Secrets manager transformers them into a user & password that are then injected into the chart values and used by Alert manager as SMTP credentials.
The monitoring stack install script will check the age of the current credentials, and if they are too old (currently older than 40 days) it will create a new credentials and update the credentials in AWS secrets manager.
If the install script logs that the credentials were rotated, we should also run the script on the other cluster (prod/remoting) to make sure both clusters use the same credentials.
Once those are switched over the old credentials should be deactivated.
To validate that the new credentials are being used, check the last used field for the new credentials in the [AWS IAM Console](https://console.aws.amazon.com/iam/home#/users/prod-monitoring-email-user?section=security_credentials)
