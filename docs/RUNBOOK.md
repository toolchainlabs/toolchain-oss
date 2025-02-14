# Handling alerts and errors

We have 3 systems that will alert us via email/slack/PagerDuty when things go wrong:

- [StatusCake](https://app.statuscake.com/) - this is an uptime monitoring service. It will fire alerts when the sites it monitors have downtime. Downtime alerts will post to slack, email, and will trigger a PagerDuty incident.

- [Prometheus](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/) - Alerts will show up in slack/email. Alerts are based on metrics collected from infra (Kubernetes & AWS) and on application logic. See [Monitoring README](./../prod/helm/observability/monitoring/README.md) for general information.
- [Sentry](https://sentry.io/organizations/toolchain/projects/) - Sentry integrates into our app code and collects unhandled exceptions. It alerts slack, email, and the list of open issue can be viewed on sentry's web dashboard.

## Handling downtime - StatusCake

Downtime can be caused by DNS, network issues (timeouts) or most commonly the site returns http errors (500x,40x) on the health check endpoints when StatusCake periodically calls it.

- Track down the errors in our logs. Depending on the service that has failed you can narrow down the logs you are looking at.
  For example, if app.toolchain.com is down, look for errors in the servicerouter app/service (logging, filter for `"kubernetes.labels.toolchain_product": "servicerouter"`)
  Do further filtering on nginx, you can filter by HTTP response code that nginx process, for example:  `logJson.status": "503"`
  See the [logging readme](./../prod/helm/observability/logging/README.md#searching--filtering-logs---in-production) for more guidance about tracking down information in production logs.

- Logging into StatusCake - login credentials are in the Toolchain 1Password account, under the devops vault.
In status cake you can see the kind of error they observed (http errors, timeouts, dns, etc…). An important piece of information from StatusCake is the exact request time , this value can be used to scope down the log search and track down errors

## Handling prometheus alerts

There are types of metrics that Prometheus collects and as a result two types of alerts: Infra & application.
There is no special tag but infra alerts will usually include an infra term from either the kubernetes domain/world: Pod, Cluster, DaemonSet, etc... or will include the name of an AWS service or system we run on AWS, for example: Lambda, Elasticsearch, Redis, etc...

All other alerts are application alerts, i.e. they are based on metrics reporter from within our code.
The alerts will show up in slack (and email) however clicking on the links will attempt to take you to the alert manager instance, which will not work.
Instead if you want to see the alert information & labels you will need to [port forward the prometheus instance](../prod/helm/observability/monitoring/README.md#how-to-access-monitoring-in-production) from the cluster firing the alert.

### Handling infra alerts

Those metrics come from different parts of our infra (mostly kubernetes and AWS) - these alerts will fire when a part of the infra is misbehaving. This can be due to the way our code is behaving. For example - memory/cpu issues, app crashes will manifest as kubernetes alerts letting us know about pod crashes, pod gets killed etc.
Another way those alerts can be triggered is if our code is misbehaving in the way it interacts 3rd part code or services, for example if the code is causing some overload in Elasticsearch which in turn causes it to crash and return errors, in which case an alert on the ES Metrics we monitor will fire.

Another kind of infra alert can happen due to outages on 3rd party services we use and depends on (AWS, PyPi, GitHub)
It is wise to check external status dashboards for those services if there is any indication/suspicion that the cause for the alert is external.

External status pages:

- [AWS](https://status.aws.amazon.com/)
- [PyPi](https://status.python.org/)
- [GitHub](https://www.githubstatus.com/)

### Handling application alerts

These are alerts based on metrics we collect in our code. They can be somewhat generic, like the [Django Prometheus](https://github.com/korfuri/django-prometheus) integration middleware or they can come from our code directly.

In the first case, there should be some application specific info in one of the alert labels, like a view name, this can be used to go to the code and probably track down logs in order to further debug the issue.
In the second case, finding the code that creates and updated the counter and figuring out what is wrong (use grep `metric name`).
It is useful to [access the Prometheus instance](../prod/helm/observability/monitoring/README.md#how-to-access-monitoring-in-production) the alert is coming from to see all information about the alert and to see the metric behavior.

## Handling errors reported via Sentry

Note that we have several projects in sentry, those are essentially buckets that events go into.
For production we currently have 3 projects:

- [toolchain](https://sentry.io/organizations/toolchain/issues/?project=1470101) - all of our backend python code for the web app, marketing (info) site go into this project.
- [toolchain-frontend](https://sentry.io/organizations/toolchain/issues/?project=1471755) - our JS SPA is configured to send errors happing with our JS (in users browsers) to this project.
- [remoting](https://sentry.io/organizations/toolchain/issues/?project=1470101) - remote cache components (proxy & storage) send errors to this project

We send almost all error to sentry, using sentry is intuitive as it will give you stack information about the failure. There are two ways to use that Info to make further debugging /investigation in case it is not obvious from the information sentry provides what went wrong.
The first approach is to use the info from the error to add a test in order to locally reproduce and debug the issue.

The other (more dangerous and complicated approach) is to use that info to repro the issue in a production shell. This can be done by connecting to the relevant pad and running the Django shell (manage.py shell_plus)
However this is very dangerous because this basically allows us to run arbitrary code in prod which can cause irreversible damage to data and can further destabilize the system.

**Use judgment when taking this route and ask for help/guidance as needed.** It is a good idea to pair with another engineer when doing that so things can be thought thru and evaluated for possible negative side effects
The same way we peer review code in PRs we should peer review the code we run via shell in prod.

## Related runbooks for handling specific alerts

- Handling 404 Error response rate errors - [Blocking volunrability scans](./blocking_scans.md)