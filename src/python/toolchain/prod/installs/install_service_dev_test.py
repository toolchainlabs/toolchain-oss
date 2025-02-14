# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import pytest
from moto import mock_secretsmanager, mock_sts

from toolchain.aws.elasticsearch_test import mock_es
from toolchain.aws.test_utils.s3_utils import TEST_REGION
from toolchain.config.services import ServiceBuildResult, ToolchainService, get_service
from toolchain.prod.installs.install_service_dev import InstallServiceDev
from toolchain.util.prod.chat_client_test import create_fake_slack_webhook_secret
from toolchain.util.prod.helm_charts import ServiceChartInfo, get_item_by_name


class TestInstallServiceDev:
    _SENTRY_DSN = "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709"
    _FAKE_ES_DOMAINS = [
        {
            "name": "jerry",
            "arn": "no-soup-for-you",
            "endpoint": "independent-george",
            "tags": {"env": "toolchain_dev", "app": "buildsense-api"},
        }
    ]

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_es(self._FAKE_ES_DOMAINS), mock_secretsmanager(), mock_sts():
            create_fake_slack_webhook_secret()
            yield

    def _create_installer(self) -> InstallServiceDev:
        installer = InstallServiceDev(aws_region=TEST_REGION, dry_run=True)
        assert installer._helm._HELM_EXECUTABLE == "no-op"  # Sanity check
        assert installer._helm.cluster_name == "puffy-shirt"
        return installer

    def _get_workflow_build_result(self, service: ToolchainService) -> ServiceBuildResult:
        return ServiceBuildResult(
            service=service,
            chart_parameters=("workflow_server_rev", "workflow_maintenance_image_rev"),
            revision="fake-version-tag",
            commit_sha="one-big-tease",
        )

    def _get_web_build_result(self, service: ToolchainService) -> ServiceBuildResult:
        return ServiceBuildResult(
            service=service,
            chart_parameters=("gunicorn_image_rev",),
            revision="fake-version-tag",
            commit_sha="bad-naked",
        )

    def test_users_ui(self) -> None:
        installer = self._create_installer()
        service = get_service("users/ui")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "users-ui",
            "toolchain_product_name": "users",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.users-ui.service",
            "toolchain_env": "toolchain_dev",
            "extra_config": {
                "LOGIN_URL_HOST": "app.toolchain.com",
                "TOOLCHAIN_GITHUB_APP_INSTALL_LINK": "https://github.com/apps/toolchain-dev/installations/new",
            },
            "server_sentry_dsn": self._SENTRY_DSN,
            "secrets": ["django-secret-key", "github-app-creds", "bitbucket-oauth-creds", "jwt-auth-secret-key"],
            "dbs": ["users"],
            "service_type": "web-ui",
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_servicerouter(self) -> None:
        installer = self._create_installer()
        service = get_service("servicerouter")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "servicerouter",
            "ingress": {"enabled": False},
            "service_location": "edge",
            "host_name": "app.toolchain.com",
            "toolchain_product_name": "servicerouter",
            "secrets": ["django-secret-key", "jwt-auth-secret-key"],
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.servicerouter.service",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "extra_config": {
                "LOGIN_URL_HOST": "app.toolchain.com",
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "assets-dev.us-east-1.toolchain.com",
                    "keys": ["dev/frontend/seinfeld/seinfeld.json", "dev/frontend/shared/shared.json"],
                },
            },
            "dbs": ["users"],
            "service_type": "web-ui",
            "resources": {
                "gunicorn": {
                    "requests": {"cpu": "20m", "ephemeral_storage": "1Gi", "memory": "256Mi"},
                    "limits": {"ephemeral_storage": "10Gi"},
                }
            },
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_users_api(self) -> None:
        installer = self._create_installer()
        service = get_service("users/api")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "users-api",
            "toolchain_product_name": "users",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.users-api.service",
            "toolchain_env": "toolchain_dev",
            "secrets": ["jwt-auth-secret-key"],
            "server_sentry_dsn": self._SENTRY_DSN,
            "extra_config": {
                "LOGIN_URL_HOST": "app.toolchain.com",
                "REMOTE_EXECUTION_CUSTOMER_SLUGS": ["seinfeld", "pantsbuild"],
                "REMOTE_CACHE_ADDRESS": "grpc://localhost:8980",
            },
            "dbs": ["users"],
            "service_type": "api",
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_buildsense_api(self) -> None:
        installer = self._create_installer()
        service = get_service("buildsense/api")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "buildsense-api",
            "toolchain_product_name": "buildsense",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.buildsense-api.service",
            "toolchain_env": "toolchain_dev",
            "service_type": "api",
            "extra_config": {
                "BUILDSENSE_BUCKET": "staging.buildstats-dev.us-east-1.toolchain.com",
                "BUILDSENSE_ELASTICSEARCH_HOST": "independent-george",
                "INFLUXDB_CONFIG": {"host": "influxdb.seinfeld.svc.cluster.local"},
            },
            "server_sentry_dsn": self._SENTRY_DSN,
            "has_static_files": False,
            "dbs": ["users", "buildsense"],
            "secrets": ["django-secret-key", "influxdb-buildsense-ro-token"],
            "resources": {
                "gunicorn": {
                    "requests": {"cpu": "20m", "ephemeral_storage": "3Gi", "memory": "256Mi"},
                    "limits": {"cpu": "800m", "ephemeral_storage": "20Gi", "memory": "3Gi"},
                }
            },
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_dependency_api(self) -> None:
        installer = self._create_installer()
        service = get_service("dependency/api")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        values = installer._get_values("seinfeld", sbr, ci)
        extra_containers = values.pop("extraContainers")

        assert values == {
            "name": "dependency-api",
            "toolchain_product_name": "dependency",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.dependency-api.service",
            "secrets": ["django-secret-key", "jwt-auth-secret-key"],
            "gunicornExtraVolumeMounts": [{"mountPath": "/data/leveldb/", "name": "leveldb-data"}],
            "serviceExtraVolumes": [{"emptyDir": {}, "name": "leveldb-data"}],
            "service_type": "api",
            "extra_config": {
                "DEPGRAPH_BASE_DIR_URL": "file:///data/leveldb/depgraph/",
                "MODULE_DATA_BASE_DIR_URL": "file:///data/leveldb/modules/",
            },
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "has_static_files": False,
            "dbs": ["users", "pypi", "dependency"],
            "resources": {
                "gunicorn": {
                    "limits": {"ephemeral_storage": "30Gi"},
                    "requests": {"cpu": "20m", "ephemeral_storage": "10Gi", "memory": "256Mi"},
                }
            },
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert len(extra_containers) == 1
        leveldb_watcher = extra_containers[0]
        image = leveldb_watcher.pop("image")
        # TODO: make this assertion resilient to changes (new versions).
        assert image == "283194185447.dkr.ecr.us-east-1.amazonaws.com/leveldb-watcher:2022-02-24.02-42-16-4eac776204fb"
        assert leveldb_watcher == {
            "name": "leveldb-watcher",
            "volumeMounts": [{"name": "leveldb-data", "mountPath": "/data/leveldb-download/"}],
            "env": [
                {"name": "PUSH_GATEWAY_URL", "value": ""},
                {"name": "PERIOD_SECS", "value": "300"},
                {
                    "name": "REMOTE_BASEDIR_URLS",
                    "value": "s3://pypi-dev.us-east-1.toolchain.com/shared/depgraph/;s3://pypi-dev.us-east-1.toolchain.com/shared/modules/",
                },
                {
                    "name": "LOCAL_BASEDIR_URLS",
                    "value": "file:///data/leveldb-download/depgraph/;file:///data/leveldb-download/modules/",
                },
                {"name": "K8S_POD_NAMESPACE", "valueFrom": {"fieldRef": {"fieldPath": "metadata.namespace"}}},
                {"name": "K8S_NODE_NAME", "valueFrom": {"fieldRef": {"fieldPath": "spec.nodeName"}}},
                {"name": "K8S_POD_NAME", "valueFrom": {"fieldRef": {"fieldPath": "metadata.name"}}},
            ],
        }
        local_dirs = get_item_by_name(leveldb_watcher["env"], "LOCAL_BASEDIR_URLS")["value"].split(";")
        remote_dirs = get_item_by_name(leveldb_watcher["env"], "REMOTE_BASEDIR_URLS")["value"].split(";")
        assert len(local_dirs) == len(remote_dirs) == 2

        # We are specifically testing that those pairs since the util/leveldb/watcher.py has no logic to make sure we download the and put
        # the data in the right place.
        assert local_dirs[0].endswith("/depgraph/")
        assert remote_dirs[0].endswith("/depgraph/")

        assert local_dirs[1].endswith("/modules/")
        assert remote_dirs[1].endswith("/modules/")

    def test_infosite(self) -> None:
        installer = self._create_installer()
        service = get_service("infosite")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        sbr.tests_images = {"infosite": "festivus"}
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "infosite",
            "service_type": "web-ui-marketing",
            "service_location": "edge",
            "host_name": "toolchain.com",
            "toolchain_product_name": "infosite",
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "ingress": {"enabled": False},
            "server_sentry_dsn": self._SENTRY_DSN,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.infosite.service",
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "toolchain_env": "toolchain_dev",
            "tests": {"enabled": True, "infosite": {"image_rev": {"ap-northeast-1": "festivus"}}},
        }

    def test_toolshed(self) -> None:
        installer = self._create_installer()
        service = get_service("toolshed")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "toolshed",
            "service_type": "admin",
            "service_location": "edge",
            "toolchain_product_name": "toolshed",
            "host_name": "toolshed.toolchainlabs.com",
            "ingress": {"enabled": False},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.toolshed.service",
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "secrets": [
                "django-secret-key",
                "toolshed-admin-github-oauth-app",
                "toolshed-cookie-salt",
                "duo-toolshed-app",
            ],
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": [
                "users",
                "buildsense",
                "scm-integration",
                "oss-metrics",
                "pants-demos",
                "payments",
                "notifications",
            ],
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_crawler_pypi_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("crawler/pypi/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        crawler_values = installer._get_values("seinfeld", sbr, ci)
        workers_values = crawler_values.pop("workers")
        assert len(workers_values) == 2
        assert crawler_values == {
            "name": "crawler-pypi-workflow",
            "toolchain_product_name": "crawler-pypi",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": ["pypi"],
            "global": {"region": "ap-northeast-1"},
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert workers_values["fetcher_values"] == {
            "worker_deployment_name": "crawler-pypi-fetcher",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.crawler-pypi-workflow.service",
            "replicas": 1,
            "extra_config": {
                "INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT": "1",
                "WEBRESOURCE_BUCKET": "pypi-dev.us-east-1.toolchain.com",
                "WORKFLOW": {"batch_size": 50, "num_executor_threads": 4, "class_names": ["PypiURLFetcher"]},
            },
        }
        assert workers_values["processor_values"] == {
            "worker_deployment_name": "crawler-pypi-processor",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.crawler-pypi-workflow.service",
            "replicas": 0,
            "extra_config": {
                "WORKFLOW": {"batch_size": 5, "num_executor_threads": 1, "class_names": ["-PypiURLFetcher"]},
                "WEBRESOURCE_BUCKET": "pypi-dev.us-east-1.toolchain.com",
            },
        }

    def test_webhooks(self) -> None:
        installer = self._create_installer()
        service = get_service("webhooks")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        sbr.tests_images = {"webhooks": "mole"}
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "webhooks",
            "ingress": {"enabled": False},
            "service_location": "edge",
            "toolchain_env": "toolchain_dev",
            "host_name": "webhooks.toolchain.com",
            "toolchain_product_name": "webhooks",
            "has_static_files": False,
            "tests": {"enabled": True, "webhooks": {"image_rev": {"ap-northeast-1": "mole"}}},
            "server_sentry_dsn": self._SENTRY_DSN,
            "service_type": "api",
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "secrets": ["github-app-webhook-secrets", "stripe-integration"],
            "global": {"region": "ap-northeast-1"},
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }

    def test_buildsense_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("buildsense/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        buildsense_values = installer._get_values("seinfeld", sbr, ci)
        workers_values = buildsense_values.pop("workers")
        assert len(workers_values) == 1
        assert buildsense_values == {
            "name": "buildsense-workflow",
            "toolchain_product_name": "buildsense",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": ["buildsense", "users"],
            "global": {"region": "ap-northeast-1"},
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert workers_values["buildsense_worker_values"] == {
            "worker_deployment_name": "buildsense-worker",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.buildsense-workflow.service",
            "replicas": 1,
            "resources": {
                "worker": {
                    "requests": {"cpu": "400m", "memory": "1Gi", "ephemeral_storage": "4Gi"},
                    "limits": {"cpu": "1800m", "memory": "3Gi", "ephemeral_storage": "20Gi"},
                }
            },
            "secrets": ["influxdb-buildsense-token"],
            "extra_config": {
                "INFLUXDB_CONFIG": {"host": "influxdb.seinfeld.svc.cluster.local"},
                "BUILDSENSE_BUCKET": "staging.buildstats-dev.us-east-1.toolchain.com",
                "BUILDSENSE_ELASTICSEARCH_HOST": "independent-george",
                "WORKFLOW": {"batch_size": 4, "num_executor_threads": 3},
            },
        }

    def test_dependency_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("dependency/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        dependency_values = installer._get_values("seinfeld", sbr, ci)
        workers_values = dependency_values.pop("workers")
        assert len(workers_values) == 1
        assert dependency_values == {
            "name": "dependency-workflow",
            "toolchain_product_name": "dependency",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": ["dependency"],
            "global": {"region": "ap-northeast-1"},
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert workers_values["dependency_worker_values"] == {
            "worker_deployment_name": "dependency-worker",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.dependency-workflow.service",
            "replicas": 1,
            "extra_config": {
                "WORKFLOW": {"num_executor_threads": 8},
                "DEPGRAPH_BASE_DIR_URL": "s3://pypi-dev.us-east-1.toolchain.com/shared/depgraph/",
                "LOCAL_DEPGRAPH_DIR_URL": "file:///sync/depgraph/",
            },
            "resources": {
                "worker": {
                    "requests": {"cpu": "80m", "memory": "512Mi", "ephemeral_storage": "6Gi"},
                    "limits": {"cpu": "800m", "memory": "1Gi", "ephemeral_storage": "12Gi"},
                }
            },
            "workerExtraVolumes": [{"name": "depgraph-local", "emptyDir": {}}],
            "workerExtraVolumeMounts": [{"name": "depgraph-local", "mountPath": "/sync/depgraph"}],
        }

    def test_users_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("users/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        users_values = installer._get_values("seinfeld", sbr, ci)
        workers_values = users_values.pop("workers")
        assert len(workers_values) == 1
        assert users_values == {
            "name": "users-workflow",
            "toolchain_product_name": "users",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": ["users"],
            "global": {"region": "ap-northeast-1"},
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert workers_values["users_worker_values"] == {
            "worker_deployment_name": "users-worker",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.users-workflow.service",
            "replicas": 1,
            "extra_config": {
                "CUSTOMER_EXPORT_S3_URL": "s3://artifacts.us-east-1.toolchain.com/dev/seinfeld/remote-cache/customers_map.json",
                "REMOTE_WORKERS_TOKENS_EXPORT_S3_URL": "s3://auth-token-mapping-dev/seinfeld/auth_token_map.json",
                "WORKFLOW": {"batch_size": 4, "num_executor_threads": 3},
            },
        }

    def test_scm_integration_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("scm-integration/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        gh_values = installer._get_values("bosco", sbr, ci)
        workers_values = gh_values.pop("workers")
        assert len(workers_values) == 1
        assert gh_values == {
            "name": "scm-integration-workflow",
            "toolchain_product_name": "scm-integration",
            "service_name": "scm-integration/workflow",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": self._SENTRY_DSN,
            "dbs": ["users", "scm-integration"],
            "global": {"region": "ap-northeast-1"},
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
        }
        assert workers_values["scm_integration_worker_values"] == {
            "worker_deployment_name": "scm-integration-worker",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.scm-integration-workflow.service",
            "secrets": ["github-app-private-key"],
            "extra_config": {
                "SCM_INTEGRATION_BUCKET": "scm-integration-dev.us-east-1.toolchain.com",
                "GITHUB_CONFIG": {
                    "app_id": "57680",
                    "public_link": "https://github.com/apps/toolchain-dev",
                },
            },
            "replicas": 1,
        }

    def test_remoting_execution(self) -> None:
        installer = self._create_installer()
        service = get_service("execution-server")
        ci = ServiceChartInfo.for_service(service)
        build_result = ServiceBuildResult(
            service=service,
            chart_parameters=("image_rev",),
            revision="fake-version-tag",
            commit_sha="tuck-or-untuck",
        )
        values = installer._get_values("pirate", build_result, ci)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "image_rev": {
                "ap-northeast-1": "fake-version-tag",
            },
            "global": {"region": "ap-northeast-1"},
            "cas_address": "remoting-storage-server-headless.pirate.svc.cluster.local:8980",
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
        }

    def test_remoting_proxy(self) -> None:
        installer = self._create_installer()
        service = get_service("proxy-server")
        ci = ServiceChartInfo.for_service(service)
        build_result = ServiceBuildResult(
            service=service,
            chart_parameters=("image_rev",),
            revision="fake-version-tag",
            commit_sha="tuck-or-untuck",
        )
        build_result.tests_images = {"setup_jwt_keys": "frogger"}
        values = installer._get_values("pirate", build_result, ci)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "auth_token_mapping": {
                "s3_bucket": "auth-token-mapping-dev",
                "s3_path": "pirate/auth_token_map.json",
                "refresh_frequency_s": 120,
            },
            "workers_auth_scheme": "dev_only_no_auth",
            "global": {"region": "ap-northeast-1"},
            "ingress": {"enabled": False},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.proxy-server.service",
            "request_log": {"deliver_stream_name": "remote-cache-dev-request-log-stream"},
            "image_rev": {"ap-northeast-1": "fake-version-tag"},
            "jwtSecrets": ["jwk-access-token-keys"],
            "proxy_backends": {
                "execution": {
                    "connections": 1,
                    "host": "remoting-execution-server.pirate.svc.cluster.local",
                    "port": 8980,
                },
                "storage": {
                    "connections": 2,
                    "host": "remoting-storage-server-headless.pirate.svc.cluster.local",
                    "port": 8980,
                },
            },
            "proxy_per_instance_backends": {},
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "tests": {
                "enabled": True,
                "casload": {"repo": "toolchainlabs/remote-api-tools-casload", "tag": "nightly"},
                "setup_jwt_keys": {"image_rev": {"ap-northeast-1": "frogger"}},
            },
            "grpc": {"concurrencyLimitPerConnection": 64, "maxConcurrentStreams": 1000},
            "backend_timeouts": {"get_action_result": 10000},
        }

    def test_remoting_storage(self) -> None:
        installer = self._create_installer()
        service = get_service("storage-server")
        ci = ServiceChartInfo.for_service(service)
        build_result = ServiceBuildResult(
            service=service,
            chart_parameters=("image_rev",),
            revision="fake-version-tag",
            commit_sha="tuck-or-untuck",
        )
        values = installer._get_values("pirate", build_result, ci)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "storage": {"base_path": "/data/dev_pirate/cas/"},
            "redis": {
                "host": "",
                "read_only_host": "",
                "num_connections": 5,
                "shards_config": {
                    "alpha": "dev-test-shard-alpha.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "beta": "dev-test-shard-bravo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "charlie": "dev-test-shard-charlie.trn9gg.ng.0001.use1.cache.amazonaws.com",
                },
                "num_replicas": 2,
            },
            "image_rev": {"ap-northeast-1": "fake-version-tag"},
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "nodeSelector": {"toolchain.instance_category": "service"},
            "sizeSplitThreshold": 131072,
            "grpc": {"concurrencyLimitPerConnection": None, "maxConcurrentStreams": 1000},
            "completeness_check_probability": 10,
            "storageModel": "sharded-redis",
            "localStorage": {
                "efsFileSystemId": "fs-071754e0e703edadb",
                "efsAccessPointId": "fsap-0e16b8ee74dad4715",
                "volumeSize": "10Gi",
            },
            "amberflo": {"aggregation_window_secs": 10},
        }

    def test_pants_depgraph_demo_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("pants-demos/depgraph/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        pddw_values = installer._get_values("bosco", sbr, ci)
        workers_values = pddw_values.pop("workers")
        assert len(workers_values) == 1
        assert pddw_values == {
            "name": "pants-demos-depgraph-workflow",
            "service_name": "pants-demos/depgraph/workflow",
            "toolchain_product_name": "pants-demos",
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "dbs": ["pants-demos"],
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "global": {"region": "ap-northeast-1"},
        }
        job_image = workers_values["pants_demos_depgraph_worker_values"]["extra_config"]["JOB_CONFIG"].pop("job_image")
        assert job_image.startswith("283194185447.dkr.ecr.us-east-1.amazonaws.com/pants-demos/depgraph-job:dev-202")
        assert workers_values["pants_demos_depgraph_worker_values"] == {
            "service_account_name": "pants-demos-depgraph-workflow",
            "target_namespace": None,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.pants-demos-depgraph-workflow.service",
            "worker_deployment_name": "pants-demos-depgraph-worker",
            "replicas": 1,
            "resources": {
                "worker": {
                    "requests": {"cpu": "30m", "memory": "512Mi", "ephemeral_storage": "512Mi"},
                    "limits": {"cpu": "300m", "memory": "1Gi", "ephemeral_storage": "3Gi"},
                }
            },
            "extra_config": {
                "JOB_CONFIG": {
                    "results_bucket": "pants-demos-dev.us-east-1.toolchain.com",
                    "results_base_path": "bosco/depgraph/github/repos/",
                    "push_gateway_url": None,
                }
            },
        }

    def test_pants_depgraph_demo_web(self) -> None:
        installer = self._create_installer()
        service = get_service("pants-demos/depgraph/web")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "pants-demos-depgraph-web",
            "toolchain_product_name": "pants-demos",
            "ecr_repo_base": "pants-demos/depgraph/web",
            "dbs": ["pants-demos"],
            "service_type": "web-ui-marketing",
            "service_location": "edge",
            "has_static_files": False,
            "ingress": {"enabled": False},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.pants-demos-depgraph-web.service",
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "resources": {"gunicorn": {"requests": {"cpu": "20m", "memory": "256Mi"}}},
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "global": {"region": "ap-northeast-1"},
            "extra_config": {
                "REPOS_DISABLE_INDEXING": [
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/6A1628168197D12B8690B4D7E776D3E2627C88EF561384444C0DD5A9B7DE7D70",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/globalpayroll",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/platform",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/insurance",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/payroll",
                ],
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "assets-dev.us-east-1.toolchain.com",
                    "keys": ["dev/pants-demo-site/seinfeld/seinfeld.json", "dev/pants-demo-site/shared/shared.json"],
                },
            },
        }

    def test_oss_metrics_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("oss-metrics/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        om_values = installer._get_values("bosco", sbr, ci)
        workers_values = om_values.pop("workers")
        assert len(workers_values) == 1
        assert om_values == {
            "name": "oss-metrics-workflow",
            "service_name": "oss-metrics/workflow",
            "toolchain_product_name": "oss-metrics",
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "dbs": ["oss-metrics"],
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["oss_metrics_worker_values"] == {
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.oss-metrics-workflow.service",
            "worker_deployment_name": "oss-metrics-worker",
            "replicas": 1,
            "secrets": ["bugout-api-key", "influxdb-pants-telemetry-token"],
            "extra_config": {
                "BUGOUT_INTEGRATION_BUCKET": "bugout-dev.us-east-1.toolchain.com",
                "GITHUB_REPO_STATS_BASE_KEY": "dev/bosco/github/statistics",
                "SCM_INTEGRATION_BUCKET": "scm-integration-dev.us-east-1.toolchain.com",
                "INFLUXDB_CONFIG": {"host": "influxdb.bosco.svc.cluster.local"},
            },
            "resources": {"worker": {"limits": {"cpu": "600m", "memory": "3Gi"}}},
        }

    def test_payments_api(self) -> None:
        installer = self._create_installer()
        service = get_service("payments/api")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_web_build_result(service)
        assert installer._get_values("seinfeld", sbr, ci) == {
            "name": "payments-api",
            "toolchain_product_name": "payments",
            "service_name": "payments/api",
            "gunicorn_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "dbs": ["users", "payments"],
            "has_static_files": False,
            "service_type": "api",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.payments-api.service",
            "secrets": ["stripe-integration"],
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "global": {"region": "ap-northeast-1"},
        }

    def test_payments_workflow(self) -> None:
        installer = self._create_installer()
        service = get_service("payments/workflow")
        ci = ServiceChartInfo.for_service(service)
        sbr = self._get_workflow_build_result(service)
        payments_values = installer._get_values("bosco", sbr, ci)
        workers_values = payments_values.pop("workers")
        assert len(workers_values) == 1
        assert payments_values == {
            "name": "payments-workflow",
            "service_name": "payments/workflow",
            "toolchain_product_name": "payments",
            "workflow_server_rev": {"ap-northeast-1": "fake-version-tag"},
            "workflow_maintenance_image_rev": {"ap-northeast-1": "fake-version-tag"},
            "dbs": ["users", "payments"],
            "toolchain_env": "toolchain_dev",
            "server_sentry_dsn": "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709",
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["payments_worker_values"] == {
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.puffy-shirt.payments-workflow.service",
            "worker_deployment_name": "payments-worker",
            "replicas": 1,
            "secrets": ["stripe-integration", "amberflo-integration"],
            "extra_config": {
                "STRIPE_CONFIG": {"default_price_id": "price_1KvR8PEfbv3GSgSdnaXqkFUF"},
                "WORKFLOW": {"worker_calls_log_level": 10},
            },
        }
