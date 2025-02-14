# Databases at Toolchain

We use Postgesql, which you can run locally in DEV or in the Kubernentes dev cluster in your namespace.
In production, we provision [AWS RDS Aurora PostgreSQL](https://aws.amazon.com/rds/aurora/postgresql-features/) compatible database clusters.

## Database routing per-app/service

We use multiple logical databases across our various services:
the users database, buildsense database, pypi database etc.

A single service might access multiple databases, and a single database might be accessed by multiple services.

In order to enforce a distinction between logical databases and the specific Django apps or services
that may use them, we centralize the information about who uses which database into this directory.

This information takes the form of [Django database routers](https://docs.djangoproject.com/en/3.0/topics/db/multi-db/).

Note that in our router implementation, a single Django app can only access a single logical database
in the context of a given service (this isn't a limitation of Django, just something we impose for our
own sanity.)  However the same app can access different logical databases when running in different
services. For example, the workflow app writes workflow state into the buildsense database when running
in the buildsense service, the maven database when running in the maven crawler service, and so on.
This allows us to reuse the workflow app for completely unrelated workflows whose state is separated
by virtue of being in different databases.

## Modifying and adding models (aka migrations)

When modifying, adding or removing models use the make migrations command to generate Django migrations.
Regardless of which model you are modifying migration can be generated via the toolshed manage.py command:

```shell
./src/python/toolchain/service/toolshed/manage.py makemigrations <django-app-name>
```

Migrations must be done in a backward compatible way meaning existing (deployed) code should be able to continue to run without modification after the migrations are applied, this means, among other things:

- no fields renames
- New fields on existing models with existing data must allow nulls and have a default value - this can be updated in a follow up to remove that limitation after the table rows have been properly backfilled
- No removal of fields or models currently in use by the application code

It is recommend to create/update the appropriate Django Model Admin classes to properly work with new & updated models.
The admin models are located under [toolshed/admin_models](../../toolshed/admin_models)

Migrations + models must ship in their own pr and that code needs to be deployed to toolshed and applied.

**Important Note:** It is important to add those model admins to toolshed, because if Toolshed doesn't reference those models then pants will not include those models in the deployed PEX file which will cause issues with the migration process.
For example, content type rows won't be created for those model which can trip up the Workflow app

Once the migrations are deployed, connect to the toolshed pod:

```shell
./src/sh/kubernetes/open_shell.sh toolshed
```

And run the migrate_all command:

```shell
./manage.py migrate_all
```

## Adding new databases

There are several steps, first in dev and then in production. You can refer to this [PR](https://github.com/toolchainlabs/toolchain/pull/4457) as complete example for the required changes.
*Note*: That PR was for reference only, it was shipped in parts to prevent deployment of toolshed to prod from requiring this DB before dev & testing was completed.

### Dev

1. Add a database router, it should inherit from PerAppDBRouter
2. Add the new router to the DBRouterRegistry._known_routers
3. Add the db to [db_names.sh](../../../sh/db/db_names.sh) - This is used to provision DBs in dev environments (local or in k8s)
4. Add your models and their tests, there are examples in our code base, look for files named `models_tests.py`, don't forget to add the django app to the conftest.py file.
5. Add the DB & Django app to toolshed toolshed/contants.py: ADMIN_DBS & ADMIN_APPS constants, respectively. If you want to be able to use the DB in dev while not including it in prod use the DEV_ONLY_ADMIN_DBS/DEV_ONLY_ADMIN_APPS constant instead of ADMIN_DBS/DEV_ONLY_ADMIN_APPS
   **Note:** Modifying ADMIN_DBS impacts prod, a DB can be adding to ADMIN_DBS only after an RDS instance was provisioned in production.
6. In order to create migrations for those run the [makemigrations command](https://docs.djangoproject.com/en/3.0/ref/django-admin/#django-admin-makemigrations) under the toolshed service with the app name provided as an argument:

   ```shell
   ./src/python/toolchain/service/toolshed/manage.py makemigrations my_new_app_label
   ```

7. [to be tested] With the migration in place, your can run the relevant db script for dev (dev_db_setup.sh or local_db_setup.sh) those script are non destructive and will just add & initialize the new database and run the migrations for it.

8. to add DB to existing services, beside the code references, you will need to add the DB in the call to `set_up_databases()` in the service settings.py and also add the db name to the `dbs` list in the service's helm chart values.yaml file.
 **Note:** Don't commit those changes to master until the DB is provisioned and ready to use in production

### Production

1. Add the DB definition in Terraform, [example](https://github.com/toolchainlabs/toolchain/pull/5832) apply changes after your changes are committed to the master branch.

2. Initialize the DB - This involves creating the database (schema) without any tables or data, creating database users for the applications to use and storing those users and their credentials in the kubernetes production cluster (prod-e1-1) as secrets in the prod & staging namespaces.
This step is handled by the `init_prod_db` script which needs to be run from the [devbox](../../../../../docs/devbox.md) as we don't expose production databases to the internet so there is no way to access them directly from your machine.

   ```shell
   ./src/python/toolchain/prod/init_aws_production_db/init_prod_db.py --db-name=<DB-NAME>
   ```

3. Enable Toolshed Access - Allow the Toolshed Admin Service access to the database by adding it to [the helm chart](https://github.com/toolchainlabs/toolchain/pull/5843) and by adding the DB to the [ADMIN_DB constants](https://github.com/toolchainlabs/toolchain/pull/5844) and the proper migration targets.

4. Deploy the Toolshed and run migrations from the toolshed pod:

   Connect to the toolshed pod:

   ```shell
   ./src/sh/kubernetes/open_shell.sh toolshed
   ```

   From the toolshed pod, run migrations:

   ```shell
   ./manage.py migrate_all
   ```

5. Check that the DB shows up via the Toolshed Admin UI (should show up as an option on the home page)

6. Deploy the services that uses the DB and test access to the DB from a shell
