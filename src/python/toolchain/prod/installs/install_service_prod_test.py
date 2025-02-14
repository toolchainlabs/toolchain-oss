# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import datetime
from unittest import mock

import pytest
from dateutil.parser import parse
from moto import mock_acm, mock_ec2, mock_elbv2, mock_secretsmanager, mock_sts

from toolchain.aws.test_utils.mock_es_client import mock_es
from toolchain.aws.test_utils.s3_utils import TEST_REGION
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.config.services import get_service
from toolchain.prod.installs.install_service_prod import InstallServiceProd
from toolchain.util.prod.chat_client_test import create_fake_slack_webhook_secret
from toolchain.util.prod.helm_charts import ServiceChartInfo, get_item_by_name
from toolchain.util.test.aws.utils import create_fake_cert, create_fake_security_group


class TestInstallServiceProd:
    _FAKE_ES_DOMAINS = [
        {
            "name": "jerry",
            "arn": "no-soup-for-you",
            "endpoint": "its-peppermint",
            "tags": {"env": "toolchain_prod", "app": "buildsense-api"},
        }
    ]

    @pytest.fixture(autouse=True)
    def _start_moto(self):
        with mock_elbv2(), mock_acm(), mock_ec2(), mock_secretsmanager(), mock_es(self._FAKE_ES_DOMAINS), mock_sts():
            create_fake_slack_webhook_secret()
            yield

    def _create_installer(self, is_staging=False) -> InstallServiceProd:
        return self._create_installer_for_namespace(namespace="staging" if is_staging else "prod")

    def _create_installer_for_namespace(self, namespace: str) -> InstallServiceProd:
        namespaces = {"staging", "prod"}
        namespaces.add(namespace)
        with mock.patch(
            "toolchain.prod.installs.install_service_prod.get_channel_for_cluster", return_value=None
        ), mock.patch(
            "toolchain.prod.installs.install_service_prod.get_namespaces_for_prod_cluster",
            return_value=tuple(sorted(namespaces)),
        ):
            installer = InstallServiceProd(
                aws_region=TEST_REGION, dry_run=True, namespace=namespace, cluster=mock.MagicMock(value="yada-yada")
            )
        # Sanity checks.
        assert installer._helm._HELM_EXECUTABLE == "no-op"
        assert installer._helm.cluster_name == "yada-yada"
        return installer

    def _assert_gunicorn_image(self, values):
        self._assert_image("gunicorn_image_rev", values)

    def _assert_workflow_image(self, values):
        self._assert_image("workflow_server_rev", values)
        self._assert_image("workflow_maintenance_image_rev", values)

    def _assert_e2e_test_image(self, values, test_name: str) -> None:
        tests = values.pop("tests")
        assert tests["enabled"]
        self._assert_image("image_rev", tests.pop(test_name))

    def _assert_image(self, image_type, values):
        image_rev_dict = values.pop(image_type)
        assert len(image_rev_dict) == 1
        image_rev = image_rev_dict["us-east-1"]
        if "prod-" in image_rev:
            image_rev = image_rev.replace("prod-", "")
        date_str, _, time_and_hash = image_rev.partition(".")
        assert isinstance(parse(date_str), datetime.datetime)
        assert len(time_and_hash) == 21

    def test_infosite_prod(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="toolchain.com")
        security_group_id_public = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        security_group_id_private = create_fake_security_group(
            region=TEST_REGION, group_name="k8s.yada-yada.vpn.ingress"
        )
        assert security_group_id_private != security_group_id_public
        installer = self._create_installer()
        chart_info = ServiceChartInfo.for_service(get_service("infosite"))
        assert chart_info.chart_name == "infosite"
        infosite_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 270
        assert tests_enabled is True
        self._assert_gunicorn_image(infosite_values)
        self._assert_e2e_test_image(infosite_values, "infosite")
        assert infosite_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert infosite_values == {
            "name": "infosite",
            "service_type": "web-ui-marketing",
            "replicas": 3,
            "host_name": "toolchain.com",
            "service_location": "edge",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.infosite.service",
            "toolchain_product_name": "infosite",
            "toolchain_env": "toolchain_prod",
            "global": {"region": "ap-northeast-1"},
            "resources": {"gunicorn": {"requests": {"cpu": "90m", "memory": "256Mi"}}},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
                "name": "infosite-ingress",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id_public},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "www.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "infosite", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    },
                    {
                        "host": "toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "infosite", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    },
                ],
            },
        }

    def test_infosite_staging(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="staging.toolchain.com")
        security_group_id_public = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        security_group_id_private = create_fake_security_group(
            region=TEST_REGION, group_name="k8s.yada-yada.vpn.ingress"
        )
        assert security_group_id_private != security_group_id_public
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("infosite"))
        assert chart_info.chart_name == "infosite"
        infosite_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_gunicorn_image(infosite_values)
        self._assert_e2e_test_image(infosite_values, "infosite")
        assert infosite_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert infosite_values == {
            "name": "infosite",
            "replicas": 1,
            "service_location": "edge",
            "service_type": "web-ui-marketing",
            "host_name": "toolchain.com",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.infosite.service",
            "toolchain_env": "toolchain_prod",
            "toolchain_product_name": "infosite",
            "global": {"region": "ap-northeast-1"},
            "resources": {"gunicorn": {"requests": {"cpu": "90m", "memory": "256Mi"}}},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "name": "infosite-ingress",
                "logs_prefix": "yada-yada",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id_public},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "staging.www.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "infosite", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    },
                    {
                        "host": "staging.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "infosite", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    },
                ],
            },
        }

    def test_servicerouter_prod(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="app.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer()
        chart_info = ServiceChartInfo.for_service(get_service("servicerouter"))
        assert chart_info.chart_name == "servicerouter"
        servicerouter_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 270
        assert tests_enabled is True
        self._assert_gunicorn_image(servicerouter_values)
        assert servicerouter_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert servicerouter_values == {
            "name": "servicerouter",
            "service_type": "web-ui",
            "replicas": 3,
            "toolchain_product_name": "servicerouter",
            "host_name": "app.toolchain.com",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.servicerouter.service",
            "secrets": ["django-secret-key", "source-maps-private-key", "jwt-auth-secret-key"],
            "service_location": "edge",
            "extra_config": {
                "JS_SENTRY_DSN": "https://2a0670a123f64072965b901207f3b87e@sentry.io/1471755",
                "LOGIN_URL_HOST": "app.toolchain.com",
                "STATIC_ASSETS_CONFIG": {
                    "public_key_id": "K2EN99357UPUXJ",
                    "bucket": "assets.us-east-1.toolchain.com",
                    "keys": ["prod/frontend/prod.json"],
                },
            },
            "dbs": ["users"],
            "resources": {
                "gunicorn": {
                    "requests": {"cpu": "150m", "ephemeral_storage": "1Gi", "memory": "512Mi"},
                    "limits": {"ephemeral_storage": "10Gi"},
                }
            },
            "toolchain_env": "toolchain_prod",
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
                "name": "servicerouter-ingress",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "app.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "servicerouter", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    def test_servicerouter_staging(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="staging.app.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("servicerouter"))
        assert chart_info.chart_name == "servicerouter"
        servicerouter_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_gunicorn_image(servicerouter_values)
        assert servicerouter_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert servicerouter_values == {
            "name": "servicerouter",
            "service_type": "web-ui",
            "replicas": 1,
            "host_name": "app.toolchain.com",
            "toolchain_product_name": "servicerouter",
            "service_location": "edge",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.servicerouter.service",
            "secrets": ["django-secret-key", "source-maps-private-key", "jwt-auth-secret-key"],
            "extra_config": {
                "JS_SENTRY_DSN": "https://2a0670a123f64072965b901207f3b87e@sentry.io/1471755",
                "LOGIN_URL_HOST": "staging.app.toolchain.com",
                "STATIC_ASSETS_CONFIG": {
                    "public_key_id": "K2EN99357UPUXJ",
                    "bucket": "assets.us-east-1.toolchain.com",
                    "keys": ["prod/frontend/staging.json"],
                },
            },
            "dbs": ["users"],
            "resources": {
                "gunicorn": {
                    "requests": {"cpu": "150m", "ephemeral_storage": "1Gi", "memory": "512Mi"},
                    "limits": {"ephemeral_storage": "10Gi"},
                }
            },
            "toolchain_env": "toolchain_prod",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "global": {"region": "ap-northeast-1"},
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
                "name": "servicerouter-ingress",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "staging.app.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "servicerouter", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_buildsense_api(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("buildsense/api"))
        assert chart_info.chart_name == "buildsense-api"
        buildsense_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 90
        assert tests_enabled is True
        self._assert_gunicorn_image(buildsense_values)

        assert buildsense_values == {
            "name": "buildsense-api",
            "toolchain_product_name": "buildsense",
            "replicas": 1 if is_staging else 3,
            "dbs": ["users", "buildsense"],
            "secrets": ["django-secret-key", "influxdb-buildsense-ro-token"],
            "service_type": "api",
            "has_static_files": False,
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "resources": {
                "gunicorn": {
                    "requests": {"cpu": "150m", "ephemeral_storage": "3Gi", "memory": "1Gi"},
                    "limits": {"cpu": "800m", "ephemeral_storage": "20Gi", "memory": "3Gi"},
                }
            },
            "extra_config": {
                "BUILDSENSE_BUCKET": "builds.buildsense.us-east-1.toolchain.com",
                "BUILDSENSE_ELASTICSEARCH_HOST": "its-peppermint",
                "INFLUXDB_CONFIG": {"host": "influxdb.prod.svc.cluster.local"},
            },
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.buildsense-api.service",
            "toolchain_env": "toolchain_prod",
            "global": {"region": "ap-northeast-1"},
        }

    def test_pypi_crawler_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("crawler/pypi/workflow"))
        assert chart_info.chart_name == "crawler-pypi-workflow"
        crawler_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(crawler_values)
        workers_values = crawler_values.pop("workers")
        assert len(workers_values) == 2
        assert crawler_values == {
            "name": "crawler-pypi-workflow",
            "toolchain_product_name": "crawler-pypi",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "dbs": ["pypi"],
            "global": {"region": "ap-northeast-1"},
        }

        assert workers_values["fetcher_values"] == {
            "worker_deployment_name": "crawler-pypi-fetcher",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.crawler-pypi-workflow.service",
            "replicas": 1,
            "resources": {
                "worker": {
                    "requests": {"cpu": "30m", "memory": "1Gi", "ephemeral_storage": "512Mi"},
                    "limits": {"cpu": "950m", "memory": "3Gi", "ephemeral_storage": "3Gi"},
                }
            },
            "extra_config": {
                "WORKFLOW": {"batch_size": 50, "num_executor_threads": 4, "class_names": ["PypiURLFetcher"]},
                "INLINE_SMALL_WEBRESOURCE_TEXT_CONTENT": "1",
                "WEBRESOURCE_KEY_PREFIX": "prod/v1",
                "WEBRESOURCE_BUCKET": "pypi.us-east-1.toolchain.com",
            },
        }

        assert workers_values["processor_values"] == {
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.crawler-pypi-workflow.service",
            "worker_deployment_name": "crawler-pypi-processor",
            "resources": {
                "worker": {
                    "requests": {"cpu": "30m", "memory": "1Gi", "ephemeral_storage": "3Gi"},
                    "limits": {"cpu": "800m", "memory": "3Gi", "ephemeral_storage": "6Gi"},
                }
            },
            "replicas": 1,
            "extra_config": {
                "WORKFLOW": {"batch_size": 5, "num_executor_threads": 1, "class_names": ["-PypiURLFetcher"]},
                "WEBRESOURCE_KEY_PREFIX": "prod/v1",
                "WEBRESOURCE_BUCKET": "pypi.us-east-1.toolchain.com",
            },
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_dependency_api(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("dependency/api"))
        assert chart_info.chart_name == "dependency-api"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 30
        assert tests_enabled is True
        self._assert_gunicorn_image(values)
        extra_containers = values.pop("extraContainers")

        assert values == {
            "name": "dependency-api",
            "toolchain_product_name": "dependency",
            "replicas": 1,
            "service_type": "api",
            "secrets": ["django-secret-key", "jwt-auth-secret-key"],
            "has_static_files": False,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.dependency-api.service",
            "gunicornExtraVolumeMounts": [{"mountPath": "/data/leveldb/", "name": "leveldb-data"}],
            "serviceExtraVolumes": [{"emptyDir": {}, "name": "leveldb-data"}],
            "extra_config": {
                "DEPGRAPH_BASE_DIR_URL": "file:///data/leveldb/depgraph/",
                "MODULE_DATA_BASE_DIR_URL": "file:///data/leveldb/modules/",
            },
            "toolchain_env": "toolchain_prod",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "dbs": ["users", "pypi", "dependency"],
            "resources": {
                "gunicorn": {
                    "limits": {"ephemeral_storage": "30Gi"},
                    "requests": {"cpu": "20m", "ephemeral_storage": "10Gi", "memory": "256Mi"},
                }
            },
            "global": {"region": "ap-northeast-1"},
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
                {
                    "name": "PUSH_GATEWAY_URL",
                    "value": "http://prod-monitoring-prometheus-pushgateway.monitoring.svc.cluster.local:9091",
                },
                {"name": "PERIOD_SECS", "value": "300"},
                {
                    "name": "REMOTE_BASEDIR_URLS",
                    "value": "s3://pypi.us-east-1.toolchain.com/prod/v1/depgraph/;s3://pypi.us-east-1.toolchain.com/prod/v1/modules/",
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

    @pytest.mark.parametrize(("is_staging", "fqdn_prefix"), [(True, "staging."), (False, "")])
    def test_toolshed(self, is_staging, fqdn_prefix):
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn=f"{fqdn_prefix}toolshed.toolchainlabs.com")
        security_group_id_private = create_fake_security_group(
            region=TEST_REGION, group_name="k8s.yada-yada.vpn.ingress"
        )
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("toolshed"))
        assert chart_info.chart_name == "toolshed"
        toolshed_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_gunicorn_image(toolshed_values)
        ingress_values = toolshed_values.pop("ingress")
        assert ingress_values == {
            "enabled": True,
            "external_ingress_sg_id": {"ap-northeast-1": security_group_id_private},
            "healthcheck_path": "/healthz",
            "logs_prefix": "yada-yada",
            "name": "toolshed-ingress",
            "rules": [
                {
                    "host": f"{fqdn_prefix}toolshed.toolchainlabs.com",
                    "http": {
                        "paths": [
                            {
                                "backend": {"service": {"name": "toolshed", "port": {"number": 80}}},
                                "path": "/",
                                "pathType": "Prefix",
                            }
                        ]
                    },
                }
            ],
            "scheme": "internal",
            "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
        }
        assert toolshed_values == {
            "name": "toolshed",
            "toolchain_product_name": "toolshed",
            "service_type": "admin",
            "service_location": "edge",
            "host_name": "toolshed.toolchainlabs.com",
            "resources": {"gunicorn": {"requests": {"cpu": "50m", "memory": "256Mi"}}},
            "secrets": [
                "django-secret-key",
                "toolshed-admin-github-oauth-app",
                "toolshed-cookie-salt",
                "duo-toolshed-app",
            ],
            "dbs": [
                "users",
                "buildsense",
                "scm-integration",
                "oss-metrics",
                "pants-demos",
                "payments",
            ],
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "replicas": 1,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.toolshed.service",
            "toolchain_env": "toolchain_prod",
            "global": {"region": "ap-northeast-1"},
        }

    def test_buildsense_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("buildsense/workflow"))
        assert chart_info.chart_name == "buildsense-workflow"
        buildsense_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(buildsense_values)
        workers_values = buildsense_values.pop("workers")
        assert len(workers_values) == 1
        assert buildsense_values == {
            "name": "buildsense-workflow",
            "toolchain_product_name": "buildsense",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "dbs": ["buildsense", "users"],
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["buildsense_worker_values"] == {
            "worker_deployment_name": "buildsense-worker",
            "replicas": 1,
            "resources": {
                "worker": {
                    "requests": {"cpu": "400m", "memory": "1Gi", "ephemeral_storage": "4Gi"},
                    "limits": {"cpu": "1800m", "memory": "3Gi", "ephemeral_storage": "20Gi"},
                }
            },
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.buildsense-workflow.service",
            "secrets": ["influxdb-buildsense-token"],
            "extra_config": {
                "INFLUXDB_CONFIG": {"host": "influxdb.prod.svc.cluster.local"},
                "BUILDSENSE_BUCKET": "builds.buildsense.us-east-1.toolchain.com",
                "BUILDSENSE_ELASTICSEARCH_HOST": "its-peppermint",
                "WORKFLOW": {"batch_size": 4, "num_executor_threads": 3},
            },
        }

    def test_webhooks_prod(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="webhooks.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer()
        chart_info = ServiceChartInfo.for_service(get_service("webhooks"))
        assert chart_info.chart_name == "webhooks"
        webhook_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 180
        assert tests_enabled is True
        self._assert_gunicorn_image(webhook_values)
        self._assert_e2e_test_image(webhook_values, "webhooks")
        assert webhook_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert webhook_values == {
            "name": "webhooks",
            "service_type": "api",
            "replicas": 2,
            "service_location": "edge",
            "toolchain_product_name": "webhooks",
            "host_name": "webhooks.toolchain.com",
            "toolchain_env": "toolchain_prod",
            "resources": {"gunicorn": {"requests": {"cpu": "50m", "memory": "256Mi"}}},
            "global": {"region": "ap-northeast-1"},
            "has_static_files": False,
            "secrets": ["github-app-webhook-secrets", "stripe-integration"],
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
                "name": "webhooks-ingress",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "webhooks.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "webhooks", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    def test_webhooks_staging(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="staging.webhooks.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("webhooks"))
        assert chart_info.chart_name == "webhooks"
        webhook_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_gunicorn_image(webhook_values)
        self._assert_e2e_test_image(webhook_values, "webhooks")
        assert webhook_values["ingress"]["logs_prefix"] == installer._helm.cluster_name == "yada-yada"
        assert webhook_values == {
            "name": "webhooks",
            "service_type": "api",
            "replicas": 1,
            "toolchain_product_name": "webhooks",
            "host_name": "webhooks.toolchain.com",
            "service_location": "edge",
            "toolchain_env": "toolchain_prod",
            "has_static_files": False,
            "resources": {"gunicorn": {"requests": {"cpu": "50m", "memory": "256Mi"}}},
            "global": {"region": "ap-northeast-1"},
            "secrets": ["github-app-webhook-secrets", "stripe-integration"],
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "ingress": {
                "enabled": True,
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
                "name": "webhooks-ingress",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "staging.webhooks.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "backend": {"service": {"name": "webhooks", "port": {"number": 80}}},
                                    "path": "/",
                                    "pathType": "Prefix",
                                }
                            ]
                        },
                    }
                ],
            },
        }

    def test_dependency_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("dependency/workflow"))
        assert chart_info.chart_name == "dependency-workflow"
        dependency_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(dependency_values)
        workers_values = dependency_values.pop("workers")
        assert len(workers_values) == 1
        assert dependency_values == {
            "name": "dependency-workflow",
            "toolchain_product_name": "dependency",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "dbs": ["dependency"],
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["dependency_worker_values"] == {
            "worker_deployment_name": "dependency-worker",
            "replicas": 1,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.dependency-workflow.service",
            "extra_config": {
                "WORKFLOW": {"num_executor_threads": 8},
                "DEPGRAPH_BASE_DIR_URL": "s3://pypi.us-east-1.toolchain.com/prod/v1/depgraph/",
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
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("users/workflow"))
        assert chart_info.chart_name == "users-workflow"
        users_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(users_values)
        workers_values = users_values.pop("workers")
        assert len(workers_values) == 1
        assert users_values == {
            "name": "users-workflow",
            "toolchain_product_name": "users",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "dbs": ["users"],
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["users_worker_values"] == {
            "worker_deployment_name": "users-worker",
            "replicas": 1,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.users-workflow.service",
            "extra_config": {
                "CUSTOMER_EXPORT_S3_URL": "s3://artifacts.us-east-1.toolchain.com/prod/remote-cache/customers_map.json",
                "REMOTE_WORKERS_TOKENS_EXPORT_S3_URL": "s3://auth-token-mapping-prod/auth_token_map.json",
                "WORKFLOW": {"batch_size": 4, "num_executor_threads": 3},
            },
        }

    def test_scm_integration_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("scm-integration/workflow"))
        assert chart_info.chart_name == "scm-integration-workflow"
        scm_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(scm_values)
        workers_values = scm_values.pop("workers")
        assert len(workers_values) == 1
        assert scm_values == {
            "name": "scm-integration-workflow",
            "toolchain_product_name": "scm-integration",
            "service_name": "scm-integration/workflow",
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "dbs": ["users", "scm-integration"],
            "global": {"region": "ap-northeast-1"},
        }
        assert workers_values["scm_integration_worker_values"] == {
            "worker_deployment_name": "scm-integration-worker",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.scm-integration-workflow.service",
            "secrets": ["github-app-private-key"],
            "extra_config": {
                "SCM_INTEGRATION_BUCKET": "scm-integration.us-east-1.toolchain.com",
                "GITHUB_CONFIG": {
                    "app_id": "89851",
                    "public_link": "https://github.com/apps/toolchain-build-system",
                },
            },
            "replicas": 1,
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_scm_integration_api(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("scm-integration/api"))
        assert chart_info.chart_name == "scm-integration-api"
        scm_integration_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 90
        assert tests_enabled is True
        self._assert_gunicorn_image(scm_integration_values)
        assert scm_integration_values == {
            "name": "scm-integration-api",
            "toolchain_product_name": "scm-integration",
            "service_name": "scm-integration/api",
            "replicas": 1 if is_staging else 3,
            "dbs": ["users", "scm-integration"],
            "has_static_files": False,
            "secrets": ["github-app-private-key", "bitbucket-app-creds"],
            "service_type": "api",
            "resources": {"gunicorn": {"requests": {"cpu": "200m", "memory": "256Mi"}}},
            "extra_config": {
                "SCM_INTEGRATION_BUCKET": "scm-integration.us-east-1.toolchain.com",
                "GITHUB_CONFIG": {
                    "app_id": "89851",
                    "public_link": "https://github.com/apps/toolchain-build-system",
                },
            },
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.scm-integration-api.service",
        }

    def test_remoting_execution_prod(self) -> None:
        installer = self._create_installer(is_staging=False)
        service = get_service("execution-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "execution-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "cas_address": "remoting-storage-server-headless.prod.svc.cluster.local:8980",
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "toolchain_env": "toolchain_prod",
        }

    def test_remoting_execution_staging(self) -> None:
        installer = self._create_installer(is_staging=True)
        service = get_service("execution-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "execution-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "cas_address": "remoting-storage-server-headless.staging.svc.cluster.local:8980",
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "toolchain_env": "toolchain_prod",
        }

    def test_remoting_proxy_prod(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="cache.toolchain.com")
        worker_cert_arn = create_fake_cert(region=TEST_REGION, fqdn="workers.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer(is_staging=False)
        service = get_service("proxy-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "proxy-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 630
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        self._assert_e2e_test_image(values, "setup_jwt_keys")
        assert values == {
            "replicas": 7,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "workers_auth_scheme": "auth_token",
            "auth_token_mapping": {
                "s3_bucket": "auth-token-mapping-prod",
                "s3_path": "auth_token_map.json",
                "refresh_frequency_s": 120,
            },
            "global": {"region": "ap-northeast-1"},
            "jwtSecrets": ["jwk-access-token-keys"],
            "request_log": {"deliver_stream_name": None},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.proxy-server.service",
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "toolchain_env": "toolchain_prod",
            "grpc": {"concurrencyLimitPerConnection": 64, "maxConcurrentStreams": 1000},
            "backend_timeouts": {"get_action_result": 10000},
            "proxy_backends": {
                "execution": {
                    "connections": 10,
                    "host": "remoting-execution-server.prod.svc.cluster.local",
                    "port": 8980,
                },
                "storage": {
                    "connections": 5,
                    "host": "remoting-storage-server-headless.prod.svc.cluster.local",
                    "port": 8980,
                },
            },
            "proxy_per_instance_backends": {},
            "workers_ingress": {"host": "workers.toolchain.com", "cert_arn": worker_cert_arn},
            "ingress": {
                "name": "remoting-proxy-server",
                "enabled": True,
                "ssl_redirect_enabled": False,
                "scheme": "internet-facing",
                "backend_protocol_version": "GRPC",
                "listen_ports": '[{"HTTPS": 443}]',
                "extra_attributes": "routing.http2.enabled=true,idle_timeout.timeout_seconds=900",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/grpc.health.v1.Health/Check",
                "healthcheck_success_codes": "12",
                "rules": [
                    {
                        "host": "cache.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {"service": {"name": "remoting-proxy-server", "port": {"number": 8980}}},
                                }
                            ]
                        },
                    }
                ],
                "logs_prefix": "yada-yada",
            },
        }

    def test_remoting_proxy_staging(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="staging.cache.toolchain.com")
        worker_cert_arn = create_fake_cert(region=TEST_REGION, fqdn="staging.workers.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer(is_staging=True)
        service = get_service("proxy-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "proxy-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        self._assert_e2e_test_image(values, "setup_jwt_keys")
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "workers_auth_scheme": "auth_token",
            "auth_token_mapping": {
                "s3_bucket": "auth-token-mapping-prod",
                "s3_path": "auth_token_map.json",
                "refresh_frequency_s": 120,
            },
            "global": {"region": "ap-northeast-1"},
            "request_log": {"deliver_stream_name": None},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.proxy-server.service",
            "jwtSecrets": ["jwk-access-token-keys"],
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "toolchain_env": "toolchain_prod",
            "grpc": {"concurrencyLimitPerConnection": 64, "maxConcurrentStreams": 1000},
            "backend_timeouts": {"get_action_result": 10000},
            "proxy_backends": {
                "execution": {
                    "connections": 10,
                    "host": "remoting-execution-server.staging.svc.cluster.local",
                    "port": 8980,
                },
                "storage": {
                    "connections": 5,
                    "host": "remoting-storage-server-headless.staging.svc.cluster.local",
                    "port": 8980,
                },
            },
            "proxy_per_instance_backends": {},
            "workers_ingress": {"host": "staging.workers.toolchain.com", "cert_arn": worker_cert_arn},
            "ingress": {
                "name": "remoting-proxy-server",
                "enabled": True,
                "ssl_redirect_enabled": False,
                "scheme": "internet-facing",
                "backend_protocol_version": "GRPC",
                "listen_ports": '[{"HTTPS": 443}]',
                "extra_attributes": "routing.http2.enabled=true,idle_timeout.timeout_seconds=900",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/grpc.health.v1.Health/Check",
                "healthcheck_success_codes": "12",
                "rules": [
                    {
                        "host": "staging.cache.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {"service": {"name": "remoting-proxy-server", "port": {"number": 8980}}},
                                }
                            ]
                        },
                    }
                ],
                "logs_prefix": "yada-yada",
            },
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_users_ui(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("users/ui"))
        assert chart_info.chart_name == "users-ui"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 90
        assert tests_enabled is True
        self._assert_gunicorn_image(values)
        assert values == {
            "name": "users-ui",
            "replicas": 1 if is_staging else 3,
            "toolchain_product_name": "users",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.users-ui.service",
            "toolchain_env": "toolchain_prod",
            "extra_config": {
                "LOGIN_URL_HOST": "staging.app.toolchain.com" if is_staging else "app.toolchain.com",
                "TOOLCHAIN_GITHUB_APP_INSTALL_LINK": "https://github.com/apps/toolchain-build-system/installations/new",
            },
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "secrets": ["django-secret-key", "github-app-creds", "bitbucket-oauth-creds", "jwt-auth-secret-key"],
            "dbs": ["users"],
            "service_type": "web-ui",
            "resources": {"gunicorn": {"requests": {"cpu": "100m", "memory": "512Mi"}}},
            "global": {"region": "ap-northeast-1"},
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_users_api(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("users/api"))
        assert chart_info.chart_name == "users-api"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 90
        assert tests_enabled is True
        self._assert_gunicorn_image(values)
        assert values == {
            "name": "users-api",
            "replicas": 1 if is_staging else 3,
            "toolchain_product_name": "users",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.users-api.service",
            "toolchain_env": "toolchain_prod",
            "extra_config": {
                "LOGIN_URL_HOST": "staging.app.toolchain.com" if is_staging else "app.toolchain.com",
                "REMOTE_EXECUTION_CUSTOMER_SLUGS": [
                    "toolchainlabs",
                    "pantsbuild",
                ],
                "REMOTE_CACHE_ADDRESS": "grpcs://staging.cache.toolchain.com:443"
                if is_staging
                else "grpcs://cache.toolchain.com:443",
            },
            "secrets": ["jwt-auth-secret-key"],
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "dbs": ["users"],
            "service_type": "api",
            "resources": {"gunicorn": {"requests": {"cpu": "100m", "memory": "512Mi"}}},
            "global": {"region": "ap-northeast-1"},
        }

    def test_scm_integration_workflow_prod(self) -> None:
        installer = self._create_installer(is_staging=False)
        chart_info = ServiceChartInfo.for_service(get_service("scm-integration/workflow"))
        assert chart_info.chart_name == "scm-integration-workflow"
        with pytest.raises(ToolchainAssertion, match="Workflow services shouldn't be deployed to prod namespace"):
            installer.calculate_values(chart_info)

    def test_buildsense_workflow_prod(self) -> None:
        installer = self._create_installer(is_staging=False)
        chart_info = ServiceChartInfo.for_service(get_service("buildsense/workflow"))
        assert chart_info.chart_name == "buildsense-workflow"
        with pytest.raises(ToolchainAssertion, match="Workflow services shouldn't be deployed to prod namespace"):
            installer.calculate_values(chart_info)

    def test_remoting_storage_prod(self) -> None:
        installer = self._create_installer(is_staging=False)
        service = get_service("storage-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "storage-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 585
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        assert values == {
            "replicas": 13,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "storage": {"base_path": "/data/cas"},
            "redis": {
                "host": "remoting-storage-2-rg-1.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "read_only_host": "remoting-storage-2-rg-1-ro.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "num_connections": 30,
                "shards_config": {
                    "alpha": "remoting-prod-sharded-shard-alpha.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "bravo": "remoting-prod-sharded-shard-bravo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "charlie": "remoting-prod-sharded-shard-charlie.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "delta": "remoting-prod-sharded-shard-delta.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "echo": "remoting-prod-sharded-shard-echo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                },
                "num_replicas": 2,
            },
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "sizeSplitThreshold": 131072,
            "grpc": {"maxConcurrentStreams": 1000, "concurrencyLimitPerConnection": None},
            "toolchain_env": "toolchain_prod",
            "completeness_check_probability": 10,
            "storageModel": "sharded-redis-fast-slow",
            "localStorage": {
                "efsFileSystemId": "fs-0da12c5381f11d884",
                "efsAccessPointId": "fsap-0c6ab63c37d1fb2fd",
                "volumeSize": "800Gi",
            },
            "amberflo": {"aggregation_window_secs": 900},
        }

    def test_remoting_storage_staging(self) -> None:
        installer = self._create_installer(is_staging=True)
        service = get_service("storage-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "storage-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "redis": {
                "host": "remoting-storage-2-rg-1.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "read_only_host": "remoting-storage-2-rg-1-ro.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "num_connections": 30,
                "shards_config": {
                    "alpha": "remoting-prod-sharded-shard-alpha.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "bravo": "remoting-prod-sharded-shard-bravo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "charlie": "remoting-prod-sharded-shard-charlie.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "delta": "remoting-prod-sharded-shard-delta.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "echo": "remoting-prod-sharded-shard-echo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                },
                "num_replicas": 2,
            },
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "sizeSplitThreshold": 131072,
            "grpc": {"maxConcurrentStreams": 1000, "concurrencyLimitPerConnection": None},
            "toolchain_env": "toolchain_prod",
            "completeness_check_probability": 10,
            "storageModel": "sharded-redis-fast-slow",
            "storage": {"base_path": "/data/cas"},
            "localStorage": {
                "efsFileSystemId": "fs-0da12c5381f11d884",
                "efsAccessPointId": "fsap-0c6ab63c37d1fb2fd",
                "volumeSize": "800Gi",
            },
            "amberflo": {"aggregation_window_secs": 900},
        }

    def test_oss_metrics_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("oss-metrics/workflow"))
        assert chart_info.chart_name == "oss-metrics-workflow"
        osm_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(osm_values)
        workers_values = osm_values.pop("workers")
        assert len(workers_values) == 1
        assert osm_values == {
            "name": "oss-metrics-workflow",
            "service_name": "oss-metrics/workflow",
            "toolchain_product_name": "oss-metrics",
            "dbs": ["oss-metrics"],
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
        }
        assert workers_values["oss_metrics_worker_values"] == {
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.oss-metrics-workflow.service",
            "worker_deployment_name": "oss-metrics-worker",
            "replicas": 1,
            "secrets": ["bugout-api-key", "influxdb-pants-telemetry-token"],
            "extra_config": {
                "BUGOUT_INTEGRATION_BUCKET": "bugout-prod.us-east-1.toolchain.com",
                "GITHUB_REPO_STATS_BASE_KEY": "prod/v1/github/statistics",
                "SCM_INTEGRATION_BUCKET": "scm-integration.us-east-1.toolchain.com",
                "INFLUXDB_CONFIG": {"host": "influxdb.prod.svc.cluster.local"},
            },
            "resources": {"worker": {"limits": {"cpu": "600m", "memory": "3Gi"}}},
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_pants_depgraph_demo_web(self, is_staging: bool) -> None:
        cert_arn = create_fake_cert(
            region=TEST_REGION, fqdn="staging.graphmyrepo.com" if is_staging else "graphmyrepo.com"
        )
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("pants-demos/depgraph/web"))
        assert chart_info.chart_name == "pants-demos-depgraph-web"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90 if is_staging else 135
        # assert tests_enabled is False
        self._assert_gunicorn_image(values)
        assert values == {
            "name": "pants-demos-depgraph-web",
            "toolchain_product_name": "pants-demos",
            "ecr_repo_base": "pants-demos/depgraph/web",
            "dbs": ["pants-demos"],
            "service_type": "web-ui-marketing",
            "service_location": "edge",
            "has_static_files": False,
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.pants-demos-depgraph-web.service",
            "resources": {"gunicorn": {"requests": {"cpu": "50m", "memory": "256Mi"}}},
            "extra_config": {
                "REPOS_DISABLE_INDEXING": [
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/6A1628168197D12B8690B4D7E776D3E2627C88EF561384444C0DD5A9B7DE7D70",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/globalpayroll",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/platform",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/insurance",
                    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/payroll",
                ],
                "STATIC_ASSETS_CONFIG": {
                    "bucket": "assets.us-east-1.toolchain.com",
                    "keys": ["prod/pants-demo-site/staging.json" if is_staging else "prod/pants-demo-site/prod.json"],
                },
                "JS_SENTRY_DSN": "https://a49a32f459944e8eb741d1244bc8d1cd@o265975.ingest.sentry.io/6249632",
            },
            "ingress": {
                "name": "pants-depgraph-demo-ingress",
                "enabled": True,
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/healthz",
                "rules": [
                    {
                        "host": "staging.www.graphmyrepo.com" if is_staging else "www.graphmyrepo.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {"name": "pants-demos-depgraph-web", "port": {"number": 80}}
                                    },
                                }
                            ]
                        },
                    },
                    {
                        "host": "staging.graphmyrepo.com" if is_staging else "graphmyrepo.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {"name": "pants-demos-depgraph-web", "port": {"number": 80}}
                                    },
                                }
                            ]
                        },
                    },
                ],
                "scheme": "internet-facing",
                "logs_prefix": "yada-yada",
            },
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "replicas": 1 if is_staging else 3,
        }

    def test_pants_depgraph_demo_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("pants-demos/depgraph/workflow"))
        assert chart_info.chart_name == "pants-demos-depgraph-workflow"
        pddw_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(pddw_values)
        workers_values = pddw_values.pop("workers")
        assert len(workers_values) == 1
        assert pddw_values == {
            "name": "pants-demos-depgraph-workflow",
            "service_name": "pants-demos/depgraph/workflow",
            "toolchain_product_name": "pants-demos",
            "dbs": ["pants-demos"],
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
        }
        job_image = workers_values["pants_demos_depgraph_worker_values"]["extra_config"]["JOB_CONFIG"].pop("job_image")
        assert job_image.startswith("283194185447.dkr.ecr.us-east-1.amazonaws.com/pants-demos/depgraph-job:prod-202")
        assert workers_values["pants_demos_depgraph_worker_values"] == {
            "service_account_name": "pants-demos-depgraph-workflow",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.pants-demos-depgraph-workflow.service",
            "worker_deployment_name": "pants-demos-depgraph-worker",
            "target_namespace": "pants-demos",
            "replicas": 1,
            "resources": {
                "worker": {
                    "requests": {"cpu": "30m", "memory": "512Mi", "ephemeral_storage": "512Mi"},
                    "limits": {"cpu": "300m", "memory": "1Gi", "ephemeral_storage": "3Gi"},
                }
            },
            "extra_config": {
                "JOB_CONFIG": {
                    "results_bucket": "pants-demos.us-east-1.toolchain.com",
                    "results_base_path": "prod/v1/depgraph/github/repos/",
                    "push_gateway_url": "http://prod-monitoring-prometheus-pushgateway.monitoring.svc.cluster.local:9091",
                }
            },
        }

    @pytest.mark.parametrize("is_staging", [True, False])
    def test_payments_api(self, is_staging: bool) -> None:
        installer = self._create_installer(is_staging=is_staging)
        chart_info = ServiceChartInfo.for_service(get_service("payments/api"))
        assert chart_info.chart_name == "payments-api"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45 if is_staging else 90
        assert tests_enabled is True
        self._assert_gunicorn_image(values)
        assert values == {
            "name": "payments-api",
            "toolchain_product_name": "payments",
            "service_name": "payments/api",
            "dbs": ["users", "payments"],
            "has_static_files": False,
            "service_type": "api",
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.payments-api.service",
            "secrets": ["stripe-integration"],
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
            "replicas": 1 if is_staging else 2,
        }

    def test_payments_workflow(self) -> None:
        installer = self._create_installer(is_staging=True)
        chart_info = ServiceChartInfo.for_service(get_service("payments/workflow"))
        assert chart_info.chart_name == "payments-workflow"
        pw_values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_workflow_image(pw_values)
        workers_values = pw_values.pop("workers")
        assert len(workers_values) == 1
        assert pw_values == {
            "name": "payments-workflow",
            "service_name": "payments/workflow",
            "toolchain_product_name": "payments",
            "dbs": ["users", "payments"],
            "global": {"region": "ap-northeast-1"},
            "server_sentry_dsn": "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101",
            "toolchain_env": "toolchain_prod",
        }
        assert workers_values["payments_worker_values"] == {
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.payments-workflow.service",
            "worker_deployment_name": "payments-worker",
            "replicas": 1,
            "secrets": ["stripe-integration", "amberflo-integration"],
            "extra_config": {
                "STRIPE_CONFIG": {"default_price_id": "price_1LhFfMEfbv3GSgSd5sE0YCSZ"},
                "WORKFLOW": {"worker_calls_log_level": 10},
            },
        }

    def test_remoting_proxy_edge(self) -> None:
        cert_arn = create_fake_cert(region=TEST_REGION, fqdn="edge.toolchain.com")
        worker_cert_arn = create_fake_cert(region=TEST_REGION, fqdn="edge.workers.toolchain.com")
        security_group_id = create_fake_security_group(region=TEST_REGION, group_name="k8s.yada-yada.ingress")
        installer = self._create_installer_for_namespace("edge")
        service = get_service("proxy-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "proxy-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 90
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        self._assert_e2e_test_image(values, "setup_jwt_keys")
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "workers_auth_scheme": "auth_token",
            "auth_token_mapping": {
                "s3_bucket": "auth-token-mapping-prod",
                "s3_path": "auth_token_map.json",
                "refresh_frequency_s": 120,
            },
            "global": {"region": "ap-northeast-1"},
            "jwtSecrets": ["jwk-access-token-keys"],
            "request_log": {"deliver_stream_name": None},
            "iam_service_role_arn": "arn:aws:iam::123456789012:role/k8s.yada-yada.proxy-server.service",
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "toolchain_env": "toolchain_prod",
            "grpc": {"concurrencyLimitPerConnection": 64, "maxConcurrentStreams": 1000},
            "backend_timeouts": {"get_action_result": 10000},
            "proxy_backends": {
                "execution": {
                    "connections": 10,
                    "host": "remoting-execution-server.edge.svc.cluster.local",
                    "port": 8980,
                },
                "storage": {
                    "connections": 5,
                    "host": "remoting-storage-server-headless.edge.svc.cluster.local",
                    "port": 8980,
                },
            },
            "proxy_per_instance_backends": {},
            "workers_ingress": {"host": "edge.workers.toolchain.com", "cert_arn": worker_cert_arn},
            "ingress": {
                "name": "remoting-proxy-server",
                "enabled": True,
                "ssl_redirect_enabled": False,
                "scheme": "internet-facing",
                "backend_protocol_version": "GRPC",
                "listen_ports": '[{"HTTPS": 443}]',
                "extra_attributes": "routing.http2.enabled=true,idle_timeout.timeout_seconds=900",
                "external_ingress_sg_id": {"ap-northeast-1": security_group_id},
                "ssl_certificate_arn": {"ap-northeast-1": cert_arn},
                "healthcheck_path": "/grpc.health.v1.Health/Check",
                "healthcheck_success_codes": "12",
                "rules": [
                    {
                        "host": "edge.toolchain.com",
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {"service": {"name": "remoting-proxy-server", "port": {"number": 8980}}},
                                }
                            ]
                        },
                    }
                ],
                "logs_prefix": "yada-yada",
            },
        }

    def test_remoting_storage_edge(self) -> None:
        installer = self._create_installer_for_namespace(namespace="edge")
        service = get_service("storage-server")
        chart_info = ServiceChartInfo.for_service(service)
        assert chart_info.chart_name == "storage-server"
        values, tests_enabled, install_timeout = installer.calculate_values(chart_info)
        assert install_timeout == 45
        assert tests_enabled is True
        self._assert_image("image_rev", values)
        assert values == {
            "replicas": 1,
            "image_registry": "283194185447.dkr.ecr.us-east-1.amazonaws.com",
            "global": {"region": "ap-northeast-1"},
            "storage": {"base_path": "/data/prod_edge/cas/"},
            "redis": {
                "host": "remoting-storage-2-rg-1.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "read_only_host": "remoting-storage-2-rg-1-ro.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "num_connections": 30,
                "shards_config": {
                    "alpha": "remoting-prod-sharded-shard-alpha.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "bravo": "remoting-prod-sharded-shard-bravo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "charlie": "remoting-prod-sharded-shard-charlie.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "delta": "remoting-prod-sharded-shard-delta.trn9gg.ng.0001.use1.cache.amazonaws.com",
                    "echo": "remoting-prod-sharded-shard-echo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                },
                "num_replicas": 2,
            },
            "server_sentry_dsn": "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518",
            "sizeSplitThreshold": 131072,
            "grpc": {"maxConcurrentStreams": 1000, "concurrencyLimitPerConnection": None},
            "toolchain_env": "toolchain_prod",
            "completeness_check_probability": 10,
            "storageModel": "sharded-redis-fast-slow",
            "localStorage": {
                "efsFileSystemId": "fs-0da12c5381f11d884",
                "efsAccessPointId": "fsap-0c6ab63c37d1fb2fd",
                "volumeSize": "800Gi",
            },
            "amberflo": {"aggregation_window_secs": 900},
        }
