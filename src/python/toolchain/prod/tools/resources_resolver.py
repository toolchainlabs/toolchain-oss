# Copyright 2019 Toolchain Labs, Inc. All rights reserved.
# Licensed under the Apache License, Version 2.0 (see LICENSE).

from __future__ import annotations

import os

from toolchain.aws.acm import ACM
from toolchain.aws.elasticsearch import ElasticSearch
from toolchain.aws.s3 import S3
from toolchain.base.toolchain_error import ToolchainAssertion
from toolchain.constants import ToolchainEnv
from toolchain.kubernetes.constants import KubernetesCluster, KubernetesProdNamespaces
from toolchain.util.prod.helm_charts import get_item_by_name

_PROD_JS_SENTRY_DSN = "https://2a0670a123f64072965b901207f3b87e@sentry.io/1471755"
SENTRY_DEV = "https://4e26a54933d04ad3b001859c19461e2c@sentry.io/1511709"
SENTRY_PROD = "https://7b280c8db9d44ab5a6623297f90cf56c@sentry.io/1470101"
SENTRY_REMOTING = "https://2494c110b60d43efbf1ca0eb45c8b849@o265975.ingest.sentry.io/5697518"
_SENTRY_PANTS_DEMOSITE_JS = "https://a49a32f459944e8eb741d1244bc8d1cd@o265975.ingest.sentry.io/6249632"
_PUSH_GATEWAY_URL = "http://prod-monitoring-prometheus-pushgateway.monitoring.svc.cluster.local:9091"
_BUILDSENSE_PROD_BUCKET = "builds.buildsense.us-east-1.toolchain.com"
_BUILDSENSE_DEV_BUCKET = "staging.buildstats-dev.us-east-1.toolchain.com"
_PYPI_CRAWL_BUCKET_DEV = "pypi-dev.us-east-1.toolchain.com"
_PYPI_CRAWL_BUCKET_PROD = "pypi.us-east-1.toolchain.com"
_PYPI_CRAWL_BUCKET_PREFIX_PROD = "prod/v1"
_SCM_INTEGRATION_BUCKET_PROD = "scm-integration.us-east-1.toolchain.com"
_SCM_INTEGRATION_BUCKET_DEV = "scm-integration-dev.us-east-1.toolchain.com"
_PROD_REMOTE_STORAGE_REDIS_HOST = "remoting-storage-2-rg-1.trn9gg.ng.0001.use1.cache.amazonaws.com"
_PROD_REMOTE_STORAGE_REDIS_HOST_READONLY = "remoting-storage-2-rg-1-ro.trn9gg.ng.0001.use1.cache.amazonaws.com"
_PROD_REDIS_SHARDS = ("alpha", "bravo", "charlie", "delta", "echo")
_PROD_SHARDED_HOST_NAME_TEMPLATE = "remoting-prod-sharded-shard-{shard_name}.trn9gg.ng.0001.use1.cache.amazonaws.com"
_DEV_REMOTE_CACHE_PROXY_DELIVERY_STREAM = "remote-cache-dev-request-log-stream"
_BUGOUT_DATA_BUCKET_PROD = "bugout-prod.us-east-1.toolchain.com"
_BUGOUT_DATA_BUCKET_DEV = "bugout-dev.us-east-1.toolchain.com"
_RENDER_EMAIL_BUCKET_DEV = "email-dev.us-east-1.toolchain.com"
_RENDER_EMAIL_BUCKET_PROD = "email-prod.us-east-1.toolchain.com"
_PANTS_DEMOSITE_BUCKET_DEV = "pants-demos-dev.us-east-1.toolchain.com"
_PANTS_DEMOSITE_BUCKET_PROD = "pants-demos.us-east-1.toolchain.com"

_AUTH_TOKEN_MAPPING_BUCKET_DEV = "auth-token-mapping-dev"
_AUTH_TOKEN_MAPPING_BUCKET_PROD = "auth-token-mapping-prod"

# TODO: We probably want to resolve those dynamically using AWS APIs
DEV_EFS_FILE_SYSTEM_ID = "fs-071754e0e703edadb"
_DEV_EFS_ACCESS_POINT_ID = "fsap-0e16b8ee74dad4715"
REMOTING_PROD_EFS_FILE_SYSTEM_ID = "fs-0da12c5381f11d884"
_REMOTING_PROD_EFS_ACCESS_POINT_ID = "fsap-0c6ab63c37d1fb2fd"


_DEV_REMOTE_STORAGE_REDIS_HOST = (
    "dev-test.trn9gg.0001.use1.cache.amazonaws.com"  # same as primary endpoint to test read-only pool support
)
_TOOLCHAIN_SPA_CONFIG_DEV = {
    "bucket": "assets-dev.us-east-1.toolchain.com",
    "path": "dev/frontend/{namespace}/{namespace}.json",
}
_TOOLCHAIN_SPA_CONFIG_PROD = {
    "public_key_id": "K2EN99357UPUXJ",  # https://console.aws.amazon.com/cloudfront/home?region=us-east-1#publickey:
    "bucket": "assets.us-east-1.toolchain.com",
    "path": "prod/frontend/{namespace}.json",
}
_PANTS_DEMO_SITE_SPA_CONFIG_DEV = {
    "bucket": "assets-dev.us-east-1.toolchain.com",
    "path": "dev/pants-demo-site/{namespace}/{namespace}.json",
}
_PANTS_DEMO_SITE_SPA_CONFIG_PROD = {
    "bucket": "assets.us-east-1.toolchain.com",
    "path": "prod/pants-demo-site/{namespace}.json",
}

PANTS_DEMO_SITE_REPOS_DISABLE_INDEXING: list[str] = [
    # rippling data
    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/6A1628168197D12B8690B4D7E776D3E2627C88EF561384444C0DD5A9B7DE7D70",
    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/globalpayroll",
    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/platform",
    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/insurance",
    "21FD7087A61ED25004465ECD0CD635EB63BD7480D94C790A18E3BC2A3F36D18A/payroll",
]
_GITHUB_APP_URL_PROD = "https://github.com/apps/toolchain-build-system"
_GITHUB_APP_URL_DEV = "https://github.com/apps/toolchain-dev"
_GITHUB_CONFIG_PROD = {"app_id": "89851", "public_link": _GITHUB_APP_URL_PROD}
_GITHUB_CONFIG_DEV = {"app_id": "57680", "public_link": _GITHUB_APP_URL_DEV}
CUSTOMER_EXPORT_S3_URL_PROD = "s3://artifacts.us-east-1.toolchain.com/prod/remote-cache/customers_map.json"
_CUSTOMER_EXPORT_S3_URL_DEV = "s3://artifacts.us-east-1.toolchain.com/dev/{namespace}/remote-cache/customers_map.json"
REMOTE_WORKERS_TOKENS_EXPORT_S3_URL_PROD = f"s3://{_AUTH_TOKEN_MAPPING_BUCKET_PROD}/auth_token_map.json"
_REMOTE_WORKERS_TOKENS_EXPORT_S3_URL_DEV = "s3://{bucket}/{namespace}/auth_token_map.json"

_STRIPE_DEFAULT_PRICE_ID_PROD = "price_1LhFfMEfbv3GSgSd5sE0YCSZ"  # https://dashboard.stripe.com/prices/price_1LhFfMEfbv3GSgSd5sE0YCSZ  99$/mo starter plan
_STRIPE_DEFAULT_PRICE_ID_DEV = (
    "price_1KvR8PEfbv3GSgSdnaXqkFUF"  # https://dashboard.stripe.com/test/products/prod_LcgVoYRbtZeS7i
)

_REMOTE_EXEC_CUSTOMERS_SLUGS_IN_PROD = ("toolchainlabs", "pantsbuild")


def resolve_resources(
    *,
    service: str,
    aws_region: str,
    toolchain_env: ToolchainEnv,
    cluster: KubernetesCluster,
    namespace: str,
    chart_values: dict,
) -> None:
    resolve_func = _RESOLVERS.get(service)
    if not resolve_func:
        return
    resolve_func(aws_region, cluster, toolchain_env, namespace, chart_values)


def _resolve_buildsense(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    es = ElasticSearch(aws_region)
    domain_endpoint = es.get_domain_endpoint(tags={"app": "buildsense-api", "env": toolchain_env.value})
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bucket = _BUILDSENSE_PROD_BUCKET
        influxdb_host = "influxdb.prod.svc.cluster.local"  # influxdb is running in the prod namespace.
    else:
        bucket = _BUILDSENSE_DEV_BUCKET
        influxdb_host = f"influxdb.{namespace}.svc.cluster.local"
    chart_values["extra_config"].update({"BUILDSENSE_ELASTICSEARCH_HOST": domain_endpoint, "BUILDSENSE_BUCKET": bucket})
    chart_values["extra_config"]["INFLUXDB_CONFIG"]["host"] = influxdb_host


def _resolve_buildsense_worker(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    _resolve_buildsense(aws_region, cluster, toolchain_env, namespace, chart_values)


def _resolve_servicerouter(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]
    namespaces = [namespace]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        spa_cfg = _TOOLCHAIN_SPA_CONFIG_PROD
        config["JS_SENTRY_DSN"] = _PROD_JS_SENTRY_DSN
        _resolve_login_url(aws_region, cluster, toolchain_env, namespace, chart_values)
    else:
        chart_values["secrets"].remove("source-maps-private-key")
        spa_cfg = _TOOLCHAIN_SPA_CONFIG_DEV
        namespaces.append("shared")
    spa_cfg = dict(spa_cfg)
    path = spa_cfg.pop("path")
    spa_cfg["keys"] = [path.format(namespace=ns) for ns in namespaces]  # type: ignore[assignment]
    config["STATIC_ASSETS_CONFIG"] = spa_cfg


def _resolve_dependency_api(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bucket = _PYPI_CRAWL_BUCKET_PROD
        prefix = _PYPI_CRAWL_BUCKET_PREFIX_PROD
        push_gateway = _PUSH_GATEWAY_URL
    else:
        bucket = _PYPI_CRAWL_BUCKET_DEV
        prefix = "shared"
        push_gateway = ""
    # Order matters, since it needs to match LOCAL_BASEDIR_URLS
    remote_urls = [
        S3.get_s3_url(bucket=bucket, key=os.path.join(prefix, "depgraph/")),
        S3.get_s3_url(bucket=bucket, key=os.path.join(prefix, "modules/")),
    ]
    container = get_item_by_name(chart_values["extraContainers"], "leveldb-watcher")
    env_var = get_item_by_name(container["env"], "REMOTE_BASEDIR_URLS")
    env_var["value"] = ";".join(remote_urls)
    env_var = get_item_by_name(container["env"], "PUSH_GATEWAY_URL")
    env_var["value"] = push_gateway


def _resolve_dependency_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    extra_config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bucket = _PYPI_CRAWL_BUCKET_PROD
        prefix = _PYPI_CRAWL_BUCKET_PREFIX_PROD
    else:
        bucket = _PYPI_CRAWL_BUCKET_DEV
        prefix = "shared"
    extra_config["DEPGRAPH_BASE_DIR_URL"] = S3.get_s3_url(bucket=bucket, key=os.path.join(prefix, "depgraph/"))


def _resolve_pypi_crawler(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    extra_config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bucket = _PYPI_CRAWL_BUCKET_PROD
        extra_config["WEBRESOURCE_KEY_PREFIX"] = _PYPI_CRAWL_BUCKET_PREFIX_PROD
    else:
        bucket = _PYPI_CRAWL_BUCKET_DEV
        del chart_values["resources"]  # Use defaults so the crawler can "fit" into the dev cluster.
    extra_config["WEBRESOURCE_BUCKET"] = bucket


def _resolve_scm_integration(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        gh_cfg = _GITHUB_CONFIG_PROD
        bucket = _SCM_INTEGRATION_BUCKET_PROD
    else:
        gh_cfg = _GITHUB_CONFIG_DEV
        bucket = _SCM_INTEGRATION_BUCKET_DEV

    config.update({"GITHUB_CONFIG": gh_cfg, "SCM_INTEGRATION_BUCKET": bucket})


def _resolve_users_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    is_prod = toolchain_env.is_prod  # type: ignore[attr-defined]
    extra_config = chart_values["extra_config"]
    extra_config["CUSTOMER_EXPORT_S3_URL"] = (
        CUSTOMER_EXPORT_S3_URL_PROD if is_prod else _CUSTOMER_EXPORT_S3_URL_DEV.format(namespace=namespace)
    )
    extra_config["REMOTE_WORKERS_TOKENS_EXPORT_S3_URL"] = (
        REMOTE_WORKERS_TOKENS_EXPORT_S3_URL_PROD
        if is_prod
        else _REMOTE_WORKERS_TOKENS_EXPORT_S3_URL_DEV.format(bucket=_AUTH_TOKEN_MAPPING_BUCKET_DEV, namespace=namespace)
    )


def _resolve_remoting_prod_common(chart_values: dict) -> None:
    chart_values.update(server_sentry_dsn=SENTRY_REMOTING)


def get_redis_host_for_env(toolchain_env: ToolchainEnv):
    return _DEV_REMOTE_STORAGE_REDIS_HOST if toolchain_env.is_dev else _PROD_REMOTE_STORAGE_REDIS_HOST_READONLY  # type: ignore


def get_efs_ids(is_prod: bool) -> dict[str, str]:
    return {
        "efsFileSystemId": REMOTING_PROD_EFS_FILE_SYSTEM_ID if is_prod else DEV_EFS_FILE_SYSTEM_ID,
        "efsAccessPointId": _REMOTING_PROD_EFS_ACCESS_POINT_ID if is_prod else _DEV_EFS_ACCESS_POINT_ID,
    }


def _resolve_remoting_execution_server(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        _resolve_remoting_prod_common(chart_values)
    chart_values["cas_address"] = f"remoting-storage-server-headless.{namespace}.svc.cluster.local:8980"


def _resolve_remoting_storage_server(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    redis_host_readonly = get_redis_host_for_env(toolchain_env)
    efs_ids = get_efs_ids(is_prod=toolchain_env.is_prod)  # type: ignore
    chart_values["localStorage"].update(efs_ids)
    if toolchain_env.is_dev:  # type: ignore
        chart_values.update(
            nodeSelector={"toolchain.instance_category": "service"},
            storageModel="sharded-redis",
        )
        chart_values["storage"]["base_path"] = f"/data/dev_{namespace}/cas/"
        chart_values["redis"].update(
            host="",
            read_only_host="",
            num_connections=5,
            shards_config={
                "alpha": "dev-test-shard-alpha.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "beta": "dev-test-shard-bravo.trn9gg.ng.0001.use1.cache.amazonaws.com",
                "charlie": "dev-test-shard-charlie.trn9gg.ng.0001.use1.cache.amazonaws.com",
            },
            num_replicas=2,
        )

    else:  # prod
        if namespace == KubernetesProdNamespaces.EDGE:
            chart_values["storage"]["base_path"] = "/data/prod_edge/cas/"
        chart_values.update(
            storageModel="sharded-redis-fast-slow",
        )
        chart_values["localStorage"]["volumeSize"] = "800Gi"
        chart_values["amberflo"].update(aggregation_window_secs=900)
        _resolve_remoting_prod_common(chart_values)
        shards = {shard: _PROD_SHARDED_HOST_NAME_TEMPLATE.format(shard_name=shard) for shard in _PROD_REDIS_SHARDS}
        chart_values["redis"].update(
            host=_PROD_REMOTE_STORAGE_REDIS_HOST,
            read_only_host=redis_host_readonly,
            num_connections=30,
            shards_config=shards,
            num_replicas=2,
        )


def _resolve_remoting_proxy_server(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    if toolchain_env.is_prod:  # type: ignore
        _resolve_remoting_prod_common(chart_values)
        workers_ingress_cfg = chart_values["workers_ingress"]
        workers_ingress_domain = workers_ingress_cfg["host"]
        if not KubernetesProdNamespaces.is_prod(namespace):
            workers_ingress_domain = f"{namespace}.{workers_ingress_domain}"
            workers_ingress_cfg["host"] = workers_ingress_domain

        worker_cert_arn = ACM(aws_region).get_cert_arn_for_domain(workers_ingress_domain)
        if not worker_cert_arn:
            raise ToolchainAssertion(f"Couldn't find cert for {workers_ingress_domain}")
        workers_ingress_cfg["cert_arn"] = worker_cert_arn
        storage_connections = 5
        chart_values["request_log"]["deliver_stream_name"] = None  # Not supported in prod yet
        if namespace == KubernetesProdNamespaces.EDGE:
            chart_values["ingress"]["rules"][0]["host"] = "edge.toolchain.com"

        chart_values["proxy_backends"]["execution"] = {
            "host": f"remoting-execution-server.{namespace}.svc.cluster.local",
            "port": 8980,
            "connections": 10,
        }

        chart_values["auth_token_mapping"].update(
            {
                "s3_bucket": _AUTH_TOKEN_MAPPING_BUCKET_PROD,
                "s3_path": "auth_token_map.json",
            }
        )

    else:
        del chart_values["workers_ingress"]
        storage_connections = 2
        chart_values["request_log"]["deliver_stream_name"] = _DEV_REMOTE_CACHE_PROXY_DELIVERY_STREAM
        chart_values["proxy_backends"]["execution"] = {
            "host": f"remoting-execution-server.{namespace}.svc.cluster.local",
            "connections": 1,
            "port": 8980,
        }

        chart_values["workers_auth_scheme"] = "dev_only_no_auth"
        chart_values["auth_token_mapping"].update(
            {
                "s3_bucket": _AUTH_TOKEN_MAPPING_BUCKET_DEV,
                "s3_path": f"{namespace}/auth_token_map.json",
            }
        )

    chart_values["proxy_backends"]["storage"].update(
        host=f"remoting-storage-server-headless.{namespace}.svc.cluster.local",
        connections=storage_connections,
        port=8980,
    )


def _resolve_toolshed(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    if toolchain_env.is_dev:  # type: ignore
        chart_values["dbs"].extend(("notifications",))


def _resolve_oss_metrics_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bugout_bucket = _BUGOUT_DATA_BUCKET_PROD
        scm_bucket = _SCM_INTEGRATION_BUCKET_PROD
        influxdb_host = "influxdb.prod.svc.cluster.local"  # influxdb is running in the prod namespace.
        scm_bucket_path = "prod/v1/github/statistics"
    else:
        bugout_bucket = _BUGOUT_DATA_BUCKET_DEV
        scm_bucket = _SCM_INTEGRATION_BUCKET_DEV
        influxdb_host = f"influxdb.{namespace}.svc.cluster.local"
        scm_bucket_path = f"dev/{namespace}/github/statistics"
    config.update(
        BUGOUT_INTEGRATION_BUCKET=bugout_bucket,
        SCM_INTEGRATION_BUCKET=scm_bucket,
        GITHUB_REPO_STATS_BASE_KEY=scm_bucket_path,
    )

    config["INFLUXDB_CONFIG"]["host"] = influxdb_host


def _resolve_notifications_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        bucket = _RENDER_EMAIL_BUCKET_PROD
    else:
        bucket = _RENDER_EMAIL_BUCKET_DEV
    config.update(
        RENDER_EMAIL_BUCKET_DEV=bucket,
    )


def _resolve_payments_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        price_id = _STRIPE_DEFAULT_PRICE_ID_PROD
    else:
        price_id = _STRIPE_DEFAULT_PRICE_ID_DEV
    config["STRIPE_CONFIG"]["default_price_id"] = price_id


def _resolve_pants_depgraph_demo_web(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    config = chart_values["extra_config"]

    namespaces = [namespace]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        spa_cfg = _PANTS_DEMO_SITE_SPA_CONFIG_PROD
        config["JS_SENTRY_DSN"] = _SENTRY_PANTS_DEMOSITE_JS
    else:
        spa_cfg = _PANTS_DEMO_SITE_SPA_CONFIG_DEV
        namespaces.append("shared")
    config["REPOS_DISABLE_INDEXING"] = PANTS_DEMO_SITE_REPOS_DISABLE_INDEXING
    spa_cfg = dict(spa_cfg)
    path = spa_cfg.pop("path")
    spa_cfg["keys"] = [path.format(namespace=ns) for ns in namespaces]  # type: ignore[assignment]
    config["STATIC_ASSETS_CONFIG"] = spa_cfg


def _resolve_pants_depgraph_demo_workflow(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    job_cfg = chart_values["extra_config"]["JOB_CONFIG"]
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        results_base_path = "prod/v1"
        bucket = _PANTS_DEMOSITE_BUCKET_PROD
        push_gateway_url = _PUSH_GATEWAY_URL
        image_tag = "prod-2023-03-14.17-14-42-6dbeb48aa664"
        chart_values["target_namespace"] = "pants-demos"
    else:
        results_base_path = namespace
        bucket = _PANTS_DEMOSITE_BUCKET_DEV
        push_gateway_url = None
        image_tag = "dev-2023-03-14.17-14-42-6dbeb48aa664"
    job_cfg.update(
        # src/python/toolchain/pants_demos/depgraph/workflow/config.py
        results_bucket=bucket,
        results_base_path=f"{results_base_path}/depgraph/github/repos/",
        job_image=f"283194185447.dkr.ecr.us-east-1.amazonaws.com/pants-demos/depgraph-job:{image_tag}",
        push_gateway_url=push_gateway_url,
    )


def _resolve_users_ui(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    _resolve_login_url(aws_region, cluster, toolchain_env, namespace, chart_values)
    if toolchain_env.is_prod:  # type: ignore[attr-defined]
        github_app_link = _GITHUB_APP_URL_PROD
    else:
        github_app_link = _GITHUB_APP_URL_DEV
    extra_cfg = chart_values["extra_config"]
    extra_cfg.update(
        {
            "TOOLCHAIN_GITHUB_APP_INSTALL_LINK": f"{github_app_link}/installations/new",
        }
    )


def _resolve_login_url(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    if toolchain_env.is_dev or KubernetesProdNamespaces.is_prod(namespace):  # type: ignore[attr-defined]
        return
    extra_env = chart_values["extra_config"]
    host_url = extra_env["LOGIN_URL_HOST"]
    extra_env["LOGIN_URL_HOST"] = f"{namespace}.{host_url}"


def _resolve_users_api(
    aws_region: str, cluster: KubernetesCluster, toolchain_env: ToolchainEnv, namespace: str, chart_values: dict
) -> None:
    _resolve_login_url(aws_region, cluster, toolchain_env, namespace, chart_values)
    extra_env = chart_values["extra_config"]
    if toolchain_env.is_dev:  # type: ignore[attr-defined]
        extra_env["REMOTE_CACHE_ADDRESS"] = "grpc://localhost:8980"
        extra_env["REMOTE_EXECUTION_CUSTOMER_SLUGS"] = ["seinfeld", "pantsbuild"]
    else:
        is_prod_ns = KubernetesProdNamespaces.is_prod(namespace)
        remote_cache_host = extra_env["REMOTE_CACHE_ADDRESS"]
        extra_env["REMOTE_EXECUTION_CUSTOMER_SLUGS"].extend(_REMOTE_EXEC_CUSTOMERS_SLUGS_IN_PROD)
        extra_env["REMOTE_CACHE_ADDRESS"] = (
            f"grpcs://{namespace}.{remote_cache_host}" if not is_prod_ns else f"grpcs://{remote_cache_host}"
        )


# Resolvers are only called by service installers (install_service_dev.py and install_service_prod.py)
# not by specific install scripts. if chart values needs to be tweaked when there is a dedicated installer,
# that should be done in the relevant installer not here.
_RESOLVERS = {
    "buildsense-api": _resolve_buildsense,
    "buildsense-workflow": _resolve_buildsense_worker,
    "servicerouter": _resolve_servicerouter,
    "dependency-api": _resolve_dependency_api,
    "dependency-workflow": _resolve_dependency_workflow,
    "crawler-pypi-workflow": _resolve_pypi_crawler,
    "scm-integration-workflow": _resolve_scm_integration,
    "scm-integration-api": _resolve_scm_integration,
    "execution-server": _resolve_remoting_execution_server,
    "storage-server": _resolve_remoting_storage_server,
    "proxy-server": _resolve_remoting_proxy_server,
    "toolshed": _resolve_toolshed,
    "users-workflow": _resolve_users_workflow,
    "oss-metrics-workflow": _resolve_oss_metrics_workflow,
    "pants-demos-depgraph-web": _resolve_pants_depgraph_demo_web,
    "pants-demos-depgraph-workflow": _resolve_pants_depgraph_demo_workflow,
    "users-api": _resolve_users_api,
    "users-ui": _resolve_users_ui,
    "notifications-workflow": _resolve_notifications_workflow,
    "payments-workflow": _resolve_payments_workflow,
}
