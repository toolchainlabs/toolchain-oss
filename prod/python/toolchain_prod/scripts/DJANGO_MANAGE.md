Running Django Management Commands in Production
================================================

It's sometimes necessary to run manual management commands against the production database.
An obvious example is running database schema migrations.

We perform such operations by connecting to a running docker container, such as an admin server,
that already has the code and the access permissions required to access the DB.

This is easy to do with Kubernetes:

- In the Kubernetes dashboard, click "Exec" on the appropriate Pod's status page.

or

- On the command line:

```kubectl <pod name> -ti [-c <container name>] <command>```

e.g.,

```kubectl exec users-pod-0 -ti -c gunicorn bash```

If the pod has only one container, you can omit the `-c <container name>` flag.

Run Management Commands
-----------------------

A quick reminder of some useful standard Django management commands:

To run a schema migration:

```bash
./manage.py migrate [--database dbname]
```

To run arbitrary python in a shell:

```bash
./manage.py shell
```

Or, an enhanced shell that automatically imports many useful classes, including all model classes:

```bash
./manage.py shell_plus
```

To run arbitrary sql in the psql client:

```bash
./manage.py dbshell
```
