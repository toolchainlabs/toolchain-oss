# Dev Ports

In production, services are subject to the Kubernetes network model. This means that that every service
(and in fact every pod) has its own IP address, so they can all serve on the same port (80 for services,
8000 for pods). Ports only need to be coordinated within a single pod (e.g., an nginx fronting a gunicorn).

However when developing we often want to run multiple services on our local machine.
For example, almost all our services require a users service for authentication.
To prevent collisions, we assign each service a fixed port.

The list of ports is maintained [here](services.json), and there is some [helper Python code](services.py)
to access the list.

When [running local services](../../service/README.md) they will select the right port automatically.

When [running dev services on Kubernetes](../../../../../prod/helm/README.md) we don't deploy any Ingress
resources for them, so the only way to connect to them is via a local port-forward.
[This script](../../../../sh/kubernetes/port_forward.sh) will create that port-forward for you, from the
dev port.

Thus, conveniently, whether running a local dev service or a remote one, you access it at `localhost:<dev port>`
in both cases.  E.g., authentication requests will be redirected to a users service at `localhost:9010`
when running in dev mode.
